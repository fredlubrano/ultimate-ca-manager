/**
 * CertificateExtensions — Shared X.509 extension display component.
 * Used by CertificateDetails, CADetails, and DiscoveryPage.
 */
import { useTranslation } from 'react-i18next'
import { ShieldCheck } from '@phosphor-icons/react'
import { Badge } from './Badge'
import { CompactSection } from './DetailCard'

const SAN_COLORS = {
  DNS: 'primary', IP: 'warning', Email: 'teal', URI: 'cyan',
  UPN: 'violet', DirName: 'orange', RegisteredID: 'secondary'
}

export function CertificateExtensions({ extensions, defaultOpen = true }) {
  const { t } = useTranslation()

  if (!extensions || Object.keys(extensions).length === 0) return null

  // Filter out subject_alt_names since it's displayed separately
  const hasNonSanExtensions = Object.keys(extensions).some(k => k !== 'subject_alt_names')
  if (!hasNonSanExtensions) return null

  return (
    <CompactSection title={t('details.extensions')} icon={ShieldCheck} iconClass="icon-bg-indigo" collapsible defaultOpen={defaultOpen}>
      <div className="space-y-3">
        {/* Basic Constraints */}
        {extensions.basic_constraints && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
              {t('details.ext.basicConstraints')}
              {extensions.basic_constraints.critical && <Badge variant="danger" size="sm">Critical</Badge>}
            </div>
            <div className="flex gap-2 text-xs">
              <Badge variant={extensions.basic_constraints.ca ? 'warning' : 'secondary'} size="sm">
                CA: {extensions.basic_constraints.ca ? 'TRUE' : 'FALSE'}
              </Badge>
              {extensions.basic_constraints.path_length !== null && extensions.basic_constraints.path_length !== undefined && (
                <Badge variant="secondary" size="sm">
                  Path Length: {extensions.basic_constraints.path_length}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Key Usage */}
        {extensions.key_usage && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
              {t('details.ext.keyUsage')}
              {extensions.key_usage.critical && <Badge variant="danger" size="sm">Critical</Badge>}
            </div>
            <div className="flex flex-wrap gap-1">
              {extensions.key_usage.usages.map(u => (
                <Badge key={u} variant="primary" size="sm">{u}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* Extended Key Usage */}
        {extensions.extended_key_usage && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
              {t('details.ext.extKeyUsage')}
              {extensions.extended_key_usage.critical && <Badge variant="danger" size="sm">Critical</Badge>}
            </div>
            <div className="flex flex-wrap gap-1">
              {extensions.extended_key_usage.usages.map(u => (
                <Badge key={u.oid} variant="teal" size="sm" title={u.oid}>{u.name}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* Subject Key Identifier */}
        {extensions.subject_key_identifier && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary">{t('details.ext.ski')}</div>
            <div className="text-2xs font-mono text-text-secondary break-all">{extensions.subject_key_identifier.value}</div>
          </div>
        )}

        {/* Authority Key Identifier */}
        {extensions.authority_key_identifier && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary">{t('details.ext.aki')}</div>
            <div className="text-2xs font-mono text-text-secondary break-all">{extensions.authority_key_identifier.key_id}</div>
          </div>
        )}

        {/* CRL Distribution Points */}
        {extensions.crl_distribution_points?.urls?.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary">{t('details.ext.crlDP')}</div>
            {extensions.crl_distribution_points.urls.map((url, i) => (
              <div key={i} className="text-2xs font-mono text-accent-primary break-all">{url}</div>
            ))}
          </div>
        )}

        {/* Authority Information Access */}
        {extensions.authority_info_access && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary">{t('details.ext.aia')}</div>
            {extensions.authority_info_access.ocsp?.map((url, i) => (
              <div key={`ocsp-${i}`} className="flex items-start gap-2 text-2xs">
                <Badge variant="secondary" size="sm" className="shrink-0">OCSP</Badge>
                <span className="font-mono text-accent-primary break-all">{url}</span>
              </div>
            ))}
            {extensions.authority_info_access.ca_issuers?.map((url, i) => (
              <div key={`ca-${i}`} className="flex items-start gap-2 text-2xs">
                <Badge variant="secondary" size="sm" className="shrink-0">CA Issuers</Badge>
                <span className="font-mono text-accent-primary break-all">{url}</span>
              </div>
            ))}
          </div>
        )}

        {/* Certificate Policies */}
        {extensions.certificate_policies?.policies?.length > 0 && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary">{t('details.ext.policies')}</div>
            {extensions.certificate_policies.policies.map((p, i) => (
              <div key={i} className="text-2xs font-mono text-text-secondary">
                {p.name || p.oid}
                {p.qualifiers?.map((q, j) => (
                  <span key={j} className="ml-2 text-accent-primary">{q.value}</span>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Name Constraints */}
        {extensions.name_constraints && (
          <div className="space-y-1">
            <div className="text-xs font-semibold text-text-primary flex items-center gap-1.5">
              {t('details.ext.nameConstraints')}
              {extensions.name_constraints.critical && <Badge variant="danger" size="sm">Critical</Badge>}
            </div>
            {extensions.name_constraints.permitted && (
              <div className="text-2xs"><span className="text-status-success font-medium">Permitted:</span> {extensions.name_constraints.permitted.join(', ')}</div>
            )}
            {extensions.name_constraints.excluded && (
              <div className="text-2xs"><span className="text-status-danger font-medium">Excluded:</span> {extensions.name_constraints.excluded.join(', ')}</div>
            )}
          </div>
        )}
      </div>
    </CompactSection>
  )
}

export function SubjectAltNames({ extensions, sanCombined }) {
  const { t } = useTranslation()
  
  const hasEntries = extensions?.subject_alt_names?.entries?.length > 0
  if (!hasEntries && !sanCombined) return null

  return (
    <CompactSection title={t('details.subjectAltNames')} icon={ShieldCheck} iconClass="icon-bg-teal">
      {hasEntries ? (
        <div className="flex flex-wrap gap-1">
          {extensions.subject_alt_names.entries.map((entry, i) => (
            <Badge key={i} variant={SAN_COLORS[entry.type] || 'secondary'} size="sm">
              <span className="font-semibold mr-1">{entry.type}:</span>{entry.value}
            </Badge>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-1">
          {sanCombined.split(',').map((s, i) => (
            <Badge key={i} variant="secondary" size="sm">{s.trim()}</Badge>
          ))}
        </div>
      )}
    </CompactSection>
  )
}
