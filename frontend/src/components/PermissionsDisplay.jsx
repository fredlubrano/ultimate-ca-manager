/**
 * Permissions Display Component
 * Shows role permissions in a clear, readable format
 */
import { Badge } from './Badge'
import { Lock, LockOpen, ShieldCheck } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'

export function PermissionsDisplay({ role, permissions = [], description }) {
  const { t } = useTranslation()

  if (!permissions || permissions.length === 0) {
    return <div className="text-sm text-text-secondary">{t('rbac.noPermissions')}</div>
  }

  // Check if admin (full access)
  if (permissions.includes('*')) {
    return (
      <div className="space-y-2">
        {description && (
          <p className="text-xs text-text-secondary">{description}</p>
        )}
        <div className="flex items-center gap-2 p-3 status-primary-bg status-primary-border border rounded-lg">
          <ShieldCheck size={20} className="status-primary-text" weight="fill" />
          <span className="text-sm font-semibold status-primary-text">{t('rbac.fullAccess')}</span>
        </div>
      </div>
    )
  }

  // Group permissions by action
  const grouped = {
    read: [],
    write: [],
    delete: [],
    admin: []
  }

  permissions.forEach(perm => {
    if (perm === 'read:*') {
      grouped.read.push(t('rbac.allResources'))
    } else if (perm === 'write:*') {
      grouped.write.push(t('rbac.allResources'))
    } else if (perm === 'delete:*') {
      grouped.delete.push(t('rbac.allResources'))
    } else if (perm.includes(':')) {
      const [action, resource] = perm.split(':')
      if (grouped[action]) {
        grouped[action].push(resource.toUpperCase())
      }
    }
  })

  return (
    <div className="space-y-3">
      {description && (
        <p className="text-xs text-text-secondary">{description}</p>
      )}
      
      <div className="space-y-2">
        {/* Read permissions */}
        {grouped.read.length > 0 && (
          <div className="p-3 stat-card-success border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <LockOpen size={16} className="status-success-text" />
              <span className="text-xs font-semibold status-success-text uppercase">{t('rbac.readAccess')}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {grouped.read.map((resource, idx) => (
                <Badge key={idx} variant="success" size="sm">
                  {resource}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Write permissions */}
        {grouped.write.length > 0 && (
          <div className="p-3 stat-card-primary border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Lock size={16} className="status-primary-text" />
              <span className="text-xs font-semibold status-primary-text uppercase">{t('rbac.writeAccess')}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {grouped.write.map((resource, idx) => (
                <Badge key={idx} variant="info" size="sm">
                  {resource}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Delete permissions */}
        {grouped.delete.length > 0 && (
          <div className="p-3 stat-card-warning border rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Lock size={16} className="status-warning-text" />
              <span className="text-xs font-semibold status-warning-text uppercase">{t('rbac.deleteAccess')}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {grouped.delete.map((resource, idx) => (
                <Badge key={idx} variant="warning" size="sm">
                  {resource}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
