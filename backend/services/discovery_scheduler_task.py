"""
Discovery Scheduler Task
Checks for scan profiles due for execution and triggers background scans.
Registered with SchedulerService — runs every 60 seconds.
"""
import logging
from datetime import datetime, timezone

from models import db, ScanProfile

logger = logging.getLogger(__name__)


class DiscoverySchedulerTask:
    """Automatic discovery scan scheduler."""

    @staticmethod
    def execute() -> None:
        """Check all enabled profiles and trigger scans for those due."""
        try:
            now = datetime.now(timezone.utc)
            due_profiles = ScanProfile.query.filter(
                ScanProfile.schedule_enabled == True,
                ScanProfile.next_scan_at <= now,
            ).all()

            if not due_profiles:
                logger.debug("No discovery profiles due for scanning")
                return

            from services.discovery_service import DiscoveryService
            from flask import current_app
            service = DiscoveryService()

            for profile in due_profiles:
                try:
                    targets = profile.targets_list
                    ports = profile.ports_list
                    if not targets:
                        logger.warning(f"Discovery profile '{profile.name}' has no targets, skipping")
                        continue

                    logger.info(f"Starting scheduled scan for profile '{profile.name}' "
                                f"({len(targets)} targets, ports {ports})")

                    service.start_scan(
                        targets=targets,
                        ports=ports,
                        profile_id=profile.id,
                        triggered_by='scheduled',
                        triggered_by_user='scheduler',
                        app=current_app._get_current_object(),
                    )

                except Exception as e:
                    logger.error(f"Error starting scheduled scan for profile "
                                 f"'{profile.name}': {e}", exc_info=True)

            logger.info(f"Discovery scheduler: triggered {len(due_profiles)} profile scan(s)")

        except Exception as e:
            logger.error(f"Error in discovery scheduler task: {e}", exc_info=True)
