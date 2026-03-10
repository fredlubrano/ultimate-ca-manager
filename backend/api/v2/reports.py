"""
Report API - UCM
Endpoints for generating and scheduling reports.
"""
from flask import Blueprint, request, Response
from auth.unified import require_auth
from utils.response import success_response, error_response
from services.report_service import ReportService
from models import db, SystemConfig
import json
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('reports_pro', __name__)

# All schedulable report types
SCHEDULABLE_REPORTS = [
    'certificate_inventory',
    'expiring_certificates',
    'ca_hierarchy',
    'audit_summary',
    'compliance_status',
    'executive_pdf',
]

DEFAULT_SCHEDULE = {
    'enabled': False,
    'frequency': 'weekly',
    'time': '08:00',
    'day_of_week': 1,  # Monday
    'day_of_month': 1,
    'recipients': [],
    'format': 'csv',
}


@bp.route('/api/v2/reports/types', methods=['GET'])
@require_auth(['read:audit'])
def list_report_types():
    """List available report types"""
    return success_response(data=ReportService.REPORT_TYPES)


@bp.route('/api/v2/reports/generate', methods=['POST'])
@require_auth(['read:audit', 'export:audit'])
def generate_report():
    """Generate a report on-demand"""
    data = request.get_json() or {}
    
    report_type = data.get('report_type')
    if not report_type:
        return error_response("report_type is required", 400)
    
    if report_type not in ReportService.REPORT_TYPES:
        return error_response(f"Unknown report type: {report_type}", 400)
    
    params = data.get('params', {})
    if params and not isinstance(params, dict):
        return error_response('Params must be an object', 400)
    
    try:
        report = ReportService.generate_report(report_type, params)
        return success_response(data=report)
    except Exception as e:
        logger.error(f'Report generation failed: {e}')
        return error_response("Report generation failed", 500)


@bp.route('/api/v2/reports/download/<report_type>', methods=['GET'])
@require_auth(['read:audit', 'export:audit'])
def download_report(report_type):
    """Download a report as CSV"""
    if report_type not in ReportService.REPORT_TYPES:
        return error_response(f"Unknown report type: {report_type}", 400)
    
    params = {
        'format': request.args.get('format', 'csv'),
        'days': int(request.args.get('days', 30)),
    }
    
    try:
        report = ReportService.generate_report(report_type, params)
        
        if params['format'] == 'csv':
            return Response(
                report['content'],
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=ucm-report-{report_type}.csv'
                }
            )
        else:
            return Response(
                report['content'],
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename=ucm-report-{report_type}.json'
                }
            )
    except Exception as e:
        logger.error(f'Report download generation failed: {e}')
        return error_response("Report generation failed", 500)


@bp.route('/api/v2/reports/executive-pdf', methods=['GET'])
@require_auth(['read:audit', 'export:audit'])
def download_executive_pdf():
    """Generate and download executive PDF report with charts."""
    try:
        from services.pdf_report_service import PDFReportService
        pdf_bytes = PDFReportService.generate_executive_report()
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=ucm-executive-report.pdf'
            }
        )
    except ImportError as e:
        logger.error(f'PDF dependencies missing: {e}')
        return error_response("PDF generation requires fpdf2. Install with: pip install fpdf2", 500)
    except Exception as e:
        logger.error(f'Executive PDF generation failed: {e}', exc_info=True)
        return error_response("Failed to generate executive report", 500)


@bp.route('/api/v2/reports/schedule', methods=['GET'])
@require_auth(['read:audit'])
def get_schedule_settings():
    """Get report schedule settings for all report types"""
    schedules = {}
    for report_key in SCHEDULABLE_REPORTS:
        config_key = f'report_schedule_{report_key}'
        raw = _get_config(config_key, '')
        if raw:
            try:
                schedules[report_key] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                schedules[report_key] = dict(DEFAULT_SCHEDULE)
        else:
            sched = dict(DEFAULT_SCHEDULE)
            # Backward compat: migrate old expiry/compliance config
            if report_key == 'expiring_certificates':
                if _get_config('report_expiry_enabled', 'false') == 'true':
                    sched['enabled'] = True
                    sched['frequency'] = 'daily'
                    try:
                        sched['recipients'] = json.loads(_get_config('report_expiry_recipients', '[]'))
                    except (json.JSONDecodeError, ValueError):
                        pass
            elif report_key == 'compliance_status':
                if _get_config('report_compliance_enabled', 'false') == 'true':
                    sched['enabled'] = True
                    sched['frequency'] = 'weekly'
                    try:
                        sched['recipients'] = json.loads(_get_config('report_compliance_recipients', '[]'))
                    except (json.JSONDecodeError, ValueError):
                        pass
            elif report_key == 'executive_pdf':
                sched['format'] = 'pdf'
                sched['frequency'] = 'monthly'
            schedules[report_key] = sched
    
    return success_response(data=schedules)


@bp.route('/api/v2/reports/schedule', methods=['PUT'])
@require_auth(['write:settings'])
def update_schedule_settings():
    """Update report schedule settings"""
    data = request.get_json() or {}
    
    for report_key in SCHEDULABLE_REPORTS:
        if report_key in data:
            sched = data[report_key]
            # Validate
            freq = sched.get('frequency', 'weekly')
            if freq not in ('daily', 'weekly', 'monthly'):
                return error_response(f"Invalid frequency for {report_key}: {freq}", 400)
            
            config_val = {
                'enabled': bool(sched.get('enabled', False)),
                'frequency': freq,
                'time': sched.get('time', '08:00'),
                'day_of_week': int(sched.get('day_of_week', 1)),
                'day_of_month': int(sched.get('day_of_month', 1)),
                'recipients': sched.get('recipients', []),
                'format': 'pdf' if report_key == 'executive_pdf' else sched.get('format', 'csv'),
            }
            _set_config(f'report_schedule_{report_key}', json.dumps(config_val))
    
    db.session.commit()
    return get_schedule_settings()


@bp.route('/api/v2/reports/send-test', methods=['POST'])
@require_auth(['write:settings'])
def send_test_report():
    """Send a test report to verify email configuration"""
    data = request.get_json() or {}
    
    report_type = data.get('report_type', 'expiring_certificates')
    recipient = data.get('recipient')
    
    if not recipient:
        return error_response("recipient email is required", 400)
    
    try:
        if report_type == 'executive_pdf':
            ReportService.send_scheduled_pdf_report([recipient])
        else:
            ReportService.send_scheduled_report(
                report_type,
                [recipient],
                {'days': 30}
            )
        return success_response(message=f"Test report sent to {recipient}")
    except Exception as e:
        logger.error(f'Failed to send test report: {e}')
        return error_response("Failed to send test report", 500)


def _get_config(key: str, default: str = '') -> str:
    """Get config value from database"""
    config = SystemConfig.query.filter_by(key=key).first()
    return config.value if config else default


def _set_config(key: str, value: str):
    """Set config value in database"""
    config = SystemConfig.query.filter_by(key=key).first()
    if config:
        config.value = value
    else:
        config = SystemConfig(key=key, value=value)
        db.session.add(config)
