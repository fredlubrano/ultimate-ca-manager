"""
Policy Evaluation Service
Evaluates certificate requests against active policies to determine
if approval is required before issuance.
"""
import json
import logging
from typing import Optional, Tuple
from models import db
from models.policy import CertificatePolicy, ApprovalRequest
from datetime import timedelta
from utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


class PolicyEvaluationService:
    """Evaluates certificate requests against policies"""

    @staticmethod
    def check_approval_required(ca_id: int, template_id: int = None) -> Optional[CertificatePolicy]:
        """
        Check if any active policy requires approval for this CA/template combination.
        
        Returns the matching policy if approval is required, None otherwise.
        Policies are checked by priority (lower number = higher priority).
        """
        query = CertificatePolicy.query.filter_by(
            is_active=True,
            requires_approval=True,
            policy_type='issuance'
        ).order_by(CertificatePolicy.priority.asc())

        policies = query.all()
        
        for policy in policies:
            # Policy with no CA scope = applies to all CAs
            if policy.ca_id is None:
                return policy
            # Policy scoped to specific CA
            if policy.ca_id == ca_id:
                # If also scoped to template, check that too
                if policy.template_id is not None:
                    if policy.template_id == template_id:
                        return policy
                else:
                    return policy
        
        return None

    @staticmethod
    def create_approval_request(
        policy: CertificatePolicy,
        request_data: dict,
        requester_id: int,
        comment: str = None
    ) -> ApprovalRequest:
        """
        Create an approval request for deferred certificate issuance.
        
        Args:
            policy: The policy that requires approval
            request_data: The full certificate request data (stored as JSON)
            requester_id: ID of the requesting user
            comment: Optional requester comment
            
        Returns:
            The created ApprovalRequest
        """
        approval = ApprovalRequest(
            request_type='certificate',
            policy_id=policy.id,
            requester_id=requester_id,
            requester_comment=comment or f"Certificate request: {request_data.get('cn', 'unknown')}",
            request_data=json.dumps(request_data),
            required_approvals=policy.min_approvers or 1,
            expires_at=utc_now() + timedelta(days=7),
        )
        db.session.add(approval)
        db.session.commit()
        
        logger.info(
            f"Approval request #{approval.id} created for CN={request_data.get('cn')} "
            f"by user #{requester_id}, policy={policy.name}"
        )
        
        return approval

    @staticmethod
    def get_request_data(approval: ApprovalRequest) -> Optional[dict]:
        """Get the stored certificate request data from an approval"""
        if not approval.request_data:
            return None
        try:
            return json.loads(approval.request_data)
        except Exception:
            return None
