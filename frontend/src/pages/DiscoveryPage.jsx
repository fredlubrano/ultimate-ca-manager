/**
 * DiscoveryPage — Certificate network discovery and scanning
 */
import { useState, useEffect, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Globe, MagnifyingGlass, Warning, CheckCircle, Lock,
  ArrowsClockwise, Network, Info, ShieldCheck, Trash,
  ChartBar
} from '@phosphor-icons/react'
import {
  ResponsiveLayout, Card, Button, Input, Select,
  LoadingSpinner, EmptyState, HelpCard, Badge, Tabs,
  CompactStats
} from '../components'
import { ResponsiveDataTable } from '../components/ui/responsive/ResponsiveDataTable'
import { discoveryService } from '../services'
import { useNotification } from '../contexts'
import { usePermission } from '../hooks'

export default function DiscoveryPage() {
  const { t } = useTranslation()
  const { showSuccess, showError, showConfirm } = useNotification()
  const { canWrite, isAdmin } = usePermission()

  // Data
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [discovered, setDiscovered] = useState([])
  const [unknownCerts, setUnknownCerts] = useState([])
  const [expiredCerts, setExpiredCerts] = useState([])
  const [stats, setStats] = useState({ total: 0, known: 0, unknown: 0, expired: 0, errors: 0 })
  const [scanResults, setScanResults] = useState([])

  // Scan form
  const [scanType, setScanType] = useState('targets')
  const [targetsText, setTargetsText] = useState('')
  const [subnet, setSubnet] = useState('')
  const [ports, setPorts] = useState('443')



  // ── Load data ─────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [allRes, unknownRes, expiredRes, statsRes] = await Promise.all([
        discoveryService.getAll(),
        discoveryService.getUnknown(),
        discoveryService.getExpired(),
        discoveryService.getStats(),
      ])
      setDiscovered(allRes.data ?? allRes ?? [])
      setUnknownCerts(unknownRes.data ?? unknownRes ?? [])
      setExpiredCerts(expiredRes.data ?? expiredRes ?? [])
      setStats(statsRes.data ?? statsRes ?? { total: 0, known: 0, unknown: 0, expired: 0, errors: 0 })
    } catch (error) {
      showError(error.message || t('discovery.errors.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [showError, t])

  useEffect(() => { loadData() }, [loadData])

  // ── Scan ──────────────────────────────────────────────────
  const handleScan = async () => {
    if (scanType === 'targets' && !targetsText.trim()) {
      return showError(t('discovery.errors.noTargets'))
    }
    if (scanType === 'subnet' && !subnet.trim()) {
      return showError(t('discovery.errors.noSubnet'))
    }

    const parsedPorts = ports.split(',').map(p => parseInt(p.trim(), 10)).filter(Boolean)
    setScanning(true)
    setScanResults([])
    try {
      let res
      if (scanType === 'targets') {
        const targets = targetsText.split('\n').map(s => s.trim()).filter(Boolean)
        res = await discoveryService.scan(targets, parsedPorts)
      } else {
        res = await discoveryService.scanSubnet(subnet.trim(), parsedPorts)
      }
      const results = res.data?.results ?? res?.results ?? []
      setScanResults(results)
      showSuccess(t('discovery.success.scanComplete', { count: results.length }))
      await loadData()
    } catch (error) {
      showError(error.message || t('discovery.errors.scanFailed'))
    } finally {
      setScanning(false)
    }
  }

  // ── Delete ────────────────────────────────────────────────
  const handleDelete = async (id) => {
    try {
      await discoveryService.delete(id)
      showSuccess(t('discovery.success.deleted'))
      await loadData()
    } catch (error) {
      showError(error.message)
    }
  }

  const handleDeleteAll = async () => {
    const confirmed = await showConfirm(t('discovery.deleteAllConfirm'), {
      variant: 'danger',
      confirmText: t('discovery.deleteAll'),
    })
    if (!confirmed) return
    try {
      await discoveryService.deleteAll()
      showSuccess(t('discovery.success.deletedAll'))
      setScanResults([])
      await loadData()
    } catch (error) {
      showError(error.message)
    }
  }

  // ── Status badge ──────────────────────────────────────────
  const StatusBadge = ({ status }) => {
    const map = { known: 'success', unknown: 'warning', error: 'danger' }
    return <Badge variant={map[status] || 'default'}>{status}</Badge>
  }

  const ExpiryCell = ({ row }) => {
    if (!row.not_after) return '-'
    const d = new Date(row.not_after)
    const days = row.days_until_expiry
    const cls = row.is_expired ? 'text-red-500' : days != null && days < 30 ? 'text-yellow-500' : ''
    return <span className={cls}>{d.toLocaleDateString()}{days != null ? ` (${days}d)` : ''}</span>
  }

  // ── Columns ───────────────────────────────────────────────
  const baseColumns = useMemo(() => [
    { key: 'target', label: t('discovery.columns.target'), sortable: true },
    { key: 'port', label: t('discovery.columns.port'), sortable: true },
    { key: 'subject', label: t('discovery.columns.subject'), sortable: true,
      render: (row) => {
        if (!row.subject) return '-'
        const cn = row.subject.match(/CN=([^,]+)/)?.[1] || row.subject
        return <span title={row.subject}>{cn}</span>
      }
    },
    { key: 'issuer', label: t('discovery.columns.issuer'), sortable: true,
      render: (row) => {
        if (!row.issuer) return '-'
        const cn = row.issuer.match(/CN=([^,]+)/)?.[1] || row.issuer
        return <span title={row.issuer}>{cn}</span>
      }
    },
    { key: 'not_after', label: t('discovery.columns.expiry'), sortable: true,
      render: (row) => <ExpiryCell row={row} />
    },
    { key: 'status', label: t('discovery.columns.status'), sortable: true,
      render: (row) => <StatusBadge status={row.status} />
    },
    { key: 'last_seen', label: t('discovery.columns.lastSeen'), sortable: true,
      render: (row) => row.last_seen ? new Date(row.last_seen).toLocaleString() : '-'
    },
  ], [t])

  const scanResultColumns = useMemo(() => [
    { key: 'target', label: t('discovery.columns.target'), sortable: true },
    { key: 'port', label: t('discovery.columns.port'), sortable: true },
    { key: 'subject', label: t('discovery.columns.subject'), sortable: true,
      render: (row) => {
        if (!row.subject) return row.error ? <span className="text-red-400">{row.error}</span> : '-'
        const cn = row.subject.match(/CN=([^,]+)/)?.[1] || row.subject
        return <span title={row.subject}>{cn}</span>
      }
    },
    { key: 'issuer', label: t('discovery.columns.issuer'), sortable: true,
      render: (row) => {
        if (!row.issuer) return '-'
        const cn = row.issuer.match(/CN=([^,]+)/)?.[1] || row.issuer
        return <span title={row.issuer}>{cn}</span>
      }
    },
    { key: 'not_after', label: t('discovery.columns.expiry'), sortable: true,
      render: (row) => row.not_after ? new Date(row.not_after).toLocaleDateString() : '-'
    },
    { key: 'fingerprint_sha256', label: 'SHA-256', sortable: false,
      render: (row) => row.fingerprint_sha256 ? <span className="font-mono text-xs">{row.fingerprint_sha256.substring(0, 16)}…</span> : '-'
    },
  ], [t])

  // ── Tab content ───────────────────────────────────────────
  const renderScanTab = () => (
    <div className="space-y-6">
      <Card>
        <div className="p-4 space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <Network size={24} className="text-accent-primary" />
            <h2 className="text-lg font-semibold">{t('discovery.scanConfiguration')}</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">{t('discovery.scanType')}</label>
              <Select
                value={scanType}
                onChange={setScanType}
                options={[
                  { value: 'targets', label: t('discovery.scanTypeTargets') },
                  { value: 'subnet', label: t('discovery.scanTypeSubnet') },
                ]}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">{t('discovery.ports')}</label>
              <Input value={ports} onChange={(e) => setPorts(e.target.value)} placeholder="443, 8443" />
            </div>
          </div>

          {scanType === 'targets' ? (
            <div>
              <label className="block text-sm font-medium mb-1">{t('discovery.targets')}</label>
              <textarea
                className="w-full rounded-md border border-border bg-bg-secondary text-text-primary px-3 py-2 text-sm font-mono min-h-[120px] focus:outline-none focus:ring-2 focus:ring-accent-primary"
                value={targetsText}
                onChange={(e) => setTargetsText(e.target.value)}
                placeholder={'netsuit.lan.pew.pet\n192.168.1.1\npve:8445'}
              />
              <p className="text-xs text-text-tertiary mt-1">{t('discovery.targetsHelp')}</p>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium mb-1">{t('discovery.subnet')}</label>
              <Input value={subnet} onChange={(e) => setSubnet(e.target.value)} placeholder="192.168.1.0/24" />
              <p className="text-xs text-text-tertiary mt-1">{t('discovery.subnetHelp')}</p>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button onClick={handleScan} disabled={scanning}>
              {scanning ? <LoadingSpinner size="sm" /> : <MagnifyingGlass size={16} />}
              <span className="ml-2">{scanning ? t('discovery.scanning') : t('discovery.scan')}</span>
            </Button>
          </div>
        </div>
      </Card>

      {/* Scan results (live) */}
      {scanResults.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">
            {t('discovery.scanResults', { count: scanResults.length })}
          </h3>
          <ResponsiveDataTable
            data={scanResults}
            columns={scanResultColumns}
            searchable
            searchKeys={['target', 'subject', 'issuer']}
            columnStorageKey="ucm-disc-scan-cols"
          />
        </div>
      )}

      <HelpCard title={t('discovery.helpTitle')} icon={<Info />}>
        <p className="text-sm mb-2">{t('discovery.helpDescription')}</p>
        <ul className="text-sm space-y-1 text-text-secondary">
          <li>• {t('discovery.helpItem1')}</li>
          <li>• {t('discovery.helpItem2')}</li>
          <li>• {t('discovery.helpItem3')}</li>
          <li>• {t('discovery.helpItem4')}</li>
        </ul>
      </HelpCard>
    </div>
  )

  const renderTableTab = (data, columns, emptyIcon, emptyTitle, emptyDesc, storageKey) => {
    if (data.length === 0) {
      return <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDesc} />
    }
    return (
      <ResponsiveDataTable
        data={data}
        columns={columns}
        searchable
        searchKeys={['target', 'subject', 'issuer', 'serial_number', 'status']}
        columnStorageKey={storageKey}
      />
    )
  }

  // ── Stats bar ─────────────────────────────────────────────
  const renderStats = () => (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      <CompactStats title={t('discovery.stats.total')} value={stats.total} icon={<Globe />} color="blue" />
      <CompactStats title={t('discovery.stats.known')} value={stats.known} icon={<CheckCircle />} color="green" />
      <CompactStats title={t('discovery.stats.unknown')} value={stats.unknown} icon={<Warning />} color="yellow" />
      <CompactStats title={t('discovery.stats.expired')} value={stats.expired} icon={<Lock />} color="red" />
      <CompactStats title={t('discovery.stats.errors')} value={stats.errors} icon={<ShieldCheck />} color="gray" />
    </div>
  )

  // ── Tabs ──────────────────────────────────────────────────
  const tabs = useMemo(() => [
    { id: 'scan', icon: <MagnifyingGlass size={16} />, label: t('discovery.tabScan'), content: renderScanTab() },
    { id: 'all', icon: <Globe size={16} />, label: t('discovery.tabAll'),
      content: renderTableTab(discovered, baseColumns, <Globe size={48} />,
        t('discovery.noDiscovered'), t('discovery.noDiscoveredDescription'), 'ucm-disc-all-cols')
    },
    { id: 'unknown', icon: <Warning size={16} />, label: `${t('discovery.tabUnknown')} (${stats.unknown})`,
      content: renderTableTab(unknownCerts, baseColumns, <ShieldCheck size={48} />,
        t('discovery.noUnknown'), t('discovery.noUnknownDescription'), 'ucm-disc-unknown-cols')
    },
    { id: 'expired', icon: <Lock size={16} />, label: `${t('discovery.tabExpired')} (${stats.expired})`,
      content: renderTableTab(expiredCerts, baseColumns, <CheckCircle size={48} />,
        t('discovery.noExpired'), t('discovery.noExpiredDescription'), 'ucm-disc-expired-cols')
    },
  ], [discovered, unknownCerts, expiredCerts, stats, scanResults, scanning, scanType, targetsText, subnet, ports, t])

  // ── Render ────────────────────────────────────────────────
  if (loading && discovered.length === 0) {
    return (
      <ResponsiveLayout>
        <div className="flex justify-center items-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      </ResponsiveLayout>
    )
  }

  return (
    <ResponsiveLayout>
      <div className="p-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold">{t('discovery.title')}</h1>
            <p className="text-text-secondary text-sm mt-1">{t('discovery.subtitle')}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={loadData} disabled={loading}>
              <ArrowsClockwise size={16} />
            </Button>
            {isAdmin && stats.total > 0 && (
              <Button variant="danger" onClick={handleDeleteAll}>
                <Trash size={16} />
                <span className="ml-1">{t('discovery.deleteAll')}</span>
              </Button>
            )}
          </div>
        </div>

        {renderStats()}

        <Tabs tabs={tabs} defaultTab="scan" />

      </div>
    </ResponsiveLayout>
  )
}
