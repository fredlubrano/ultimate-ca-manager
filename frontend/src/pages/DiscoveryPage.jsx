/**
 * DiscoveryPage v2 — Scan profiles, async scanning, results, history
 * Uses sidebar tab layout (same as Settings/Operations)
 */
import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Globe, MagnifyingGlass, ShieldCheck, Warning, Clock,
  ArrowsClockwise, Network, Trash, Play, Plus,
  ChartBar, ListBullets, ClockCounterClockwise, FolderOpen,
  CheckCircle, XCircle, Pencil, CalendarBlank
} from '@phosphor-icons/react'
import {
  ResponsiveLayout, Card, Button, Input, Badge, Modal, Textarea, Select,
  LoadingSpinner, EmptyState,
  CompactSection
} from '../components'
import { ResponsiveDataTable } from '../components/ui/responsive/ResponsiveDataTable'
import { ConfirmModal } from '../components/FormModal'
import { discoveryService } from '../services'
import { useNotification } from '../contexts'
import { usePermission, useWebSocket } from '../hooks'

export default function DiscoveryPage() {
  const { t } = useTranslation()
  const { showSuccess, showError } = useNotification()
  const { isAdmin } = usePermission()
  const { subscribe } = useWebSocket({ showToasts: false })

  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [stats, setStats] = useState({ total: 0, managed: 0, unmanaged: 0, expired: 0, expiring_soon: 0, errors: 0 })
  const [profiles, setProfiles] = useState([])
  const [discovered, setDiscovered] = useState([])
  const [discoveredTotal, setDiscoveredTotal] = useState(0)
  const [runs, setRuns] = useState([])
  const [runsTotal, setRunsTotal] = useState(0)

  // Scan state
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [profileFilter, setProfileFilter] = useState('')

  // Modals
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [editingProfile, setEditingProfile] = useState(null)
  const [showAdHocScan, setShowAdHocScan] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  // ── Tabs config (sidebar layout) ──────────────────
  const TABS = [
    { id: 'overview', label: t('discovery.tabOverview'), icon: ChartBar, color: 'icon-bg-blue' },
    { id: 'profiles', label: t('discovery.tabProfiles'), icon: FolderOpen, color: 'icon-bg-violet' },
    { id: 'discovered', label: `${t('discovery.tabDiscovered')} (${discoveredTotal})`, icon: Globe, color: 'icon-bg-teal' },
    { id: 'history', label: t('discovery.tabHistory'), icon: ClockCounterClockwise, color: 'icon-bg-orange' },
  ]

  const TAB_GROUPS = [
    { labelKey: 'discovery.groups.monitoring', tabs: ['overview', 'discovered'], color: 'icon-bg-blue' },
    { labelKey: 'discovery.groups.configuration', tabs: ['profiles', 'history'], color: 'icon-bg-violet' },
  ]

  // ── Load data ─────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const res = await discoveryService.getStats()
      setStats(res.data ?? res)
    } catch { /* silent */ }
  }, [])

  const loadProfiles = useCallback(async () => {
    try {
      const res = await discoveryService.getProfiles()
      setProfiles(res.data ?? res ?? [])
    } catch { /* silent */ }
  }, [])

  const loadDiscovered = useCallback(async () => {
    try {
      const params = { limit: 200 }
      if (statusFilter) params.status = statusFilter
      if (profileFilter) params.profile_id = profileFilter
      const res = await discoveryService.getAll(params)
      const data = res.data ?? res
      setDiscovered(data.items ?? data ?? [])
      setDiscoveredTotal(data.total ?? 0)
    } catch { /* silent */ }
  }, [statusFilter, profileFilter])

  const loadRuns = useCallback(async () => {
    try {
      const res = await discoveryService.getRuns({ limit: 50 })
      const data = res.data ?? res
      setRuns(data.items ?? data ?? [])
      setRunsTotal(data.total ?? 0)
    } catch { /* silent */ }
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([loadStats(), loadProfiles(), loadDiscovered(), loadRuns()])
    setLoading(false)
  }, [loadStats, loadProfiles, loadDiscovered, loadRuns])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => { loadDiscovered() }, [loadDiscovered])

  // ── WebSocket events ──────────────────────────────
  useEffect(() => {
    const unsub1 = subscribe('discovery.scan_started', (data) => {
      setScanning(true)
      setScanProgress({ total: data?.total_targets ?? 0, scanned: 0, found: 0 })
    })
    const unsub2 = subscribe('discovery.scan_progress', (data) => {
      setScanProgress(prev => ({
        ...prev,
        scanned: data?.targets_scanned ?? 0,
        found: data?.certs_found ?? 0,
      }))
    })
    const unsub3 = subscribe('discovery.scan_complete', () => {
      setScanning(false)
      setScanProgress(null)
      loadAll()
    })
    return () => { unsub1(); unsub2(); unsub3() }
  }, [subscribe, loadAll])

  // ── Profile CRUD ──────────────────────────────────
  const handleSaveProfile = async (formData) => {
    try {
      if (editingProfile) {
        await discoveryService.updateProfile(editingProfile.id, formData)
        showSuccess(t('discovery.success.profileUpdated'))
      } else {
        await discoveryService.createProfile(formData)
        showSuccess(t('discovery.success.profileCreated'))
      }
      setShowProfileForm(false)
      setEditingProfile(null)
      loadProfiles()
    } catch (error) {
      showError(error.message || t('discovery.errors.saveFailed'))
    }
  }

  const handleDeleteProfile = async (id) => {
    try {
      await discoveryService.deleteProfile(id)
      showSuccess(t('discovery.success.profileDeleted'))
      loadProfiles()
    } catch (error) {
      showError(error.message)
    }
  }

  const handleScanProfile = async (profileId) => {
    try {
      setScanning(true)
      await discoveryService.scanProfile(profileId)
    } catch (error) {
      setScanning(false)
      showError(error.message || t('discovery.errors.scanFailed'))
    }
  }

  // ── Ad-hoc scan ───────────────────────────────────
  const handleAdHocScan = async (formData) => {
    try {
      setScanning(true)
      setShowAdHocScan(false)
      if (formData.subnet) {
        await discoveryService.scanSubnet(formData.subnet, formData.ports)
      } else {
        await discoveryService.scan(formData.targets, formData.ports)
      }
    } catch (error) {
      setScanning(false)
      showError(error.message || t('discovery.errors.scanFailed'))
    }
  }

  // ── Delete discovered ─────────────────────────────
  const handleDeleteDiscovered = async (id) => {
    try {
      await discoveryService.delete(id)
      showSuccess(t('discovery.success.deleted'))
      loadDiscovered()
      loadStats()
    } catch (error) {
      showError(error.message)
    }
  }

  const handleDeleteAll = async () => {
    try {
      await discoveryService.deleteAll()
      showSuccess(t('discovery.success.deletedAll'))
      setDeleteConfirm(null)
      loadAll()
    } catch (error) {
      showError(error.message)
    }
  }

  // ── Render active tab content ─────────────────────
  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <OverviewTab
            stats={stats}
            profiles={profiles}
            runs={runs}
            scanning={scanning}
            scanProgress={scanProgress}
            onScanProfile={handleScanProfile}
            onQuickScan={() => setShowAdHocScan(true)}
            t={t}
          />
        )
      case 'profiles':
        return (
          <ProfilesTab
            profiles={profiles}
            onEdit={(p) => { setEditingProfile(p); setShowProfileForm(true) }}
            onDelete={handleDeleteProfile}
            onScan={handleScanProfile}
            onCreate={() => { setEditingProfile(null); setShowProfileForm(true) }}
            scanning={scanning}
            isAdmin={isAdmin}
            t={t}
          />
        )
      case 'discovered':
        return (
          <DiscoveredTab
            discovered={discovered}
            total={discoveredTotal}
            statusFilter={statusFilter}
            onStatusFilter={setStatusFilter}
            profiles={profiles}
            profileFilter={profileFilter}
            onProfileFilter={setProfileFilter}
            onDelete={handleDeleteDiscovered}
            onDeleteAll={() => setDeleteConfirm('all')}
            isAdmin={isAdmin}
            t={t}
          />
        )
      case 'history':
        return <HistoryTab runs={runs} total={runsTotal} t={t} />
      default:
        return null
    }
  }

  if (loading) {
    return (
      <ResponsiveLayout>
        <LoadingSpinner size="lg" />
      </ResponsiveLayout>
    )
  }

  return (
    <>
      <ResponsiveLayout
        title={t('discovery.title')}
        subtitle={t('discovery.subtitle')}
        icon={Globe}
        tabs={TABS}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tabLayout="sidebar"
        tabGroups={TAB_GROUPS}
        actions={
          <div className="flex items-center gap-2">
            {scanning && scanProgress && (
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <ArrowsClockwise size={16} className="animate-spin text-accent-primary" />
                <span>{scanProgress.scanned}/{scanProgress.total}</span>
              </div>
            )}
            <Button
              variant="secondary"
              onClick={() => setShowAdHocScan(true)}
              disabled={scanning}
              icon={<MagnifyingGlass size={16} />}
            >
              {t('discovery.quickScan')}
            </Button>
            {isAdmin && (
              <Button
                onClick={() => { setEditingProfile(null); setShowProfileForm(true) }}
                icon={<Plus size={16} />}
              >
                {t('discovery.newProfile')}
              </Button>
            )}
          </div>
        }
      >
        {renderContent()}
      </ResponsiveLayout>

      {/* Profile Form Modal */}
      {showProfileForm && (
        <ProfileFormModal
          profile={editingProfile}
          onSave={handleSaveProfile}
          onClose={() => { setShowProfileForm(false); setEditingProfile(null) }}
          t={t}
        />
      )}

      {/* Ad-hoc Scan Modal */}
      {showAdHocScan && (
        <AdHocScanModal
          onScan={handleAdHocScan}
          onClose={() => setShowAdHocScan(false)}
          t={t}
        />
      )}

      {/* Delete All Confirm */}
      <ConfirmModal
        open={deleteConfirm === 'all'}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={handleDeleteAll}
        title={t('discovery.deleteAllConfirm')}
        variant="danger"
      />
    </>
  )
}

// ═══════════════════════════════════════════════════
// Overview Tab
// ═══════════════════════════════════════════════════
function OverviewTab({ stats, profiles, runs, scanning, scanProgress, onScanProfile, onQuickScan, t }) {
  const recentRuns = runs.slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={Globe} label={t('discovery.stats.total')} value={stats.total}
          color="text-accent-primary" bgClass="icon-bg-blue"
        />
        <StatCard
          icon={ShieldCheck} label={t('discovery.stats.managed')} value={stats.managed}
          color="text-status-success" bgClass="icon-bg-emerald"
        />
        <StatCard
          icon={Warning} label={t('discovery.stats.unmanaged')} value={stats.unmanaged}
          color="text-status-warning" bgClass="icon-bg-amber"
        />
        <StatCard
          icon={XCircle} label={t('discovery.stats.expired')} value={stats.expired}
          color="text-status-error" bgClass="icon-bg-rose"
        />
      </div>

      {/* Scan Progress */}
      {scanning && scanProgress && (
        <Card className="p-4">
          <div className="flex items-center gap-3 mb-2">
            <ArrowsClockwise size={20} className="animate-spin text-accent-primary" />
            <span className="font-medium">{t('discovery.scanInProgress')}</span>
          </div>
          <div className="w-full bg-bg-tertiary rounded-full h-2">
            <div
              className="bg-accent-primary h-2 rounded-full transition-all duration-300"
              style={{ width: `${scanProgress.total ? (scanProgress.scanned / scanProgress.total * 100) : 0}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-secondary mt-1">
            <span>{scanProgress.scanned}/{scanProgress.total} {t('discovery.targets')}</span>
            <span>{scanProgress.found} {t('discovery.certsFound')}</span>
          </div>
        </Card>
      )}

      {/* Quick scan profiles */}
      {profiles.length > 0 && (
        <CompactSection title={t('discovery.scanProfiles')} icon={FolderOpen}>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {profiles.map(p => (
              <Card key={p.id} className="p-4 flex items-center justify-between">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{p.name}</div>
                  <div className="text-xs text-text-tertiary">
                    {(p.targets || []).length} {t('discovery.targets')} · {(p.ports || []).join(', ')}
                  </div>
                  {p.schedule_enabled && (
                    <div className="flex items-center gap-1 text-xs text-status-success mt-1">
                      <CalendarBlank size={12} />
                      <span>{t('discovery.everyNMin', { n: p.schedule_interval_minutes || 1440 })}</span>
                    </div>
                  )}
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onScanProfile(p.id)}
                  disabled={scanning}
                  icon={<Play size={14} />}
                >
                  {t('discovery.scan')}
                </Button>
              </Card>
            ))}
          </div>
        </CompactSection>
      )}

      {/* Recent scans */}
      {recentRuns.length > 0 && (
        <CompactSection title={t('discovery.recentScans')} icon={ClockCounterClockwise}>
          <div className="space-y-2">
            {recentRuns.map(run => (
              <Card key={run.id} className="p-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <RunStatusBadge status={run.status} />
                  <div>
                    <div className="text-sm font-medium">
                      {run.profile_name || t('discovery.adHocScan')}
                    </div>
                    <div className="text-xs text-text-tertiary">
                      {new Date(run.started_at).toLocaleString()} · {run.triggered_by}
                    </div>
                  </div>
                </div>
                <div className="text-sm text-text-secondary">
                  {run.certs_found ?? 0} {t('discovery.certsFound')}
                  {run.new_certs > 0 && (
                    <Badge variant="info" size="sm" className="ml-2">+{run.new_certs} {t('common.new')}</Badge>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </CompactSection>
      )}

      {/* Empty state */}
      {profiles.length === 0 && recentRuns.length === 0 && !scanning && (
        <EmptyState
          icon={Network}
          title={t('discovery.noResults')}
          description={t('discovery.noResultsDescription')}
          action={
            <Button onClick={onQuickScan} icon={<MagnifyingGlass size={16} />}>
              {t('discovery.quickScan')}
            </Button>
          }
        />
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════
// Profiles Tab
// ═══════════════════════════════════════════════════
function ProfilesTab({ profiles, onEdit, onDelete, onScan, onCreate, scanning, isAdmin, t }) {
  const columns = [
    { key: 'name', label: t('common.name'), sortable: true },
    {
      key: 'targets', label: t('discovery.targets'),
      render: (val) => <span className="text-xs">{(val || []).length} {t('discovery.targets')}</span>
    },
    {
      key: 'ports', label: t('discovery.ports'),
      render: (val) => <span className="text-xs font-mono">{(val || [443]).join(', ')}</span>
    },
    {
      key: 'schedule_enabled', label: t('discovery.schedule'),
      render: (val, row) => val ? (
        <Badge variant="success" size="sm">
          {t('discovery.everyNMin', { n: row.schedule_interval_minutes || 1440 })}
        </Badge>
      ) : (
        <span className="text-text-tertiary text-xs">{t('common.disabled')}</span>
      )
    },
    {
      key: 'last_scan_at', label: t('discovery.lastScan'),
      render: (val) => val
        ? <span className="text-xs">{new Date(val).toLocaleString()}</span>
        : <span className="text-text-tertiary text-xs">{t('common.never')}</span>
    },
    {
      key: 'actions', label: t('common.actions'), width: 120,
      render: (_, row) => (
        <div className="flex items-center gap-1 justify-end">
          <Button
            variant="ghost" size="sm" onClick={() => onScan(row.id)}
            disabled={scanning} icon={<Play size={14} />}
            title={t('discovery.scan')}
          />
          {isAdmin && (
            <>
              <Button
                variant="ghost" size="sm" onClick={() => onEdit(row)}
                icon={<Pencil size={14} />} title={t('common.edit')}
              />
              <Button
                variant="ghost" size="sm" onClick={() => onDelete(row.id)}
                icon={<Trash size={14} />} className="text-status-error"
                title={t('common.delete')}
              />
            </>
          )}
        </div>
      )
    },
  ]

  if (profiles.length === 0) {
    return (
      <EmptyState
        icon={FolderOpen}
        title={t('discovery.noProfiles')}
        description={t('discovery.noProfilesDescription')}
        action={
          isAdmin && (
            <Button onClick={onCreate} icon={<Plus size={16} />}>
              {t('discovery.newProfile')}
            </Button>
          )
        }
      />
    )
  }

  return <ResponsiveDataTable columns={columns} data={profiles} pageSize={20} />
}

// ═══════════════════════════════════════════════════
// Discovered Certs Tab
// ═══════════════════════════════════════════════════
function DiscoveredTab({
  discovered, total, statusFilter, onStatusFilter,
  profiles, profileFilter, onProfileFilter,
  onDelete, onDeleteAll, isAdmin, t
}) {
  const statusOptions = [
    { value: '', label: t('common.all') },
    { value: 'managed', label: t('discovery.stats.managed') },
    { value: 'unmanaged', label: t('discovery.stats.unmanaged') },
    { value: 'error', label: t('common.error') },
  ]

  const columns = [
    { key: 'target', label: t('discovery.columns.target'), sortable: true },
    { key: 'port', label: t('discovery.columns.port'), width: 70 },
    {
      key: 'subject', label: t('discovery.columns.subject'), sortable: true,
      render: (val) => <span className="font-mono text-xs truncate max-w-[200px] block">{val || '-'}</span>
    },
    {
      key: 'issuer', label: t('discovery.columns.issuer'),
      render: (val) => <span className="text-xs truncate max-w-[150px] block text-text-secondary">{val || '-'}</span>
    },
    {
      key: 'not_after', label: t('discovery.columns.expiry'),
      sortable: true,
      render: (val) => {
        if (!val) return '-'
        const d = new Date(val)
        const days = Math.ceil((d - new Date()) / 86400000)
        return (
          <div className="text-xs">
            <div>{d.toLocaleDateString()}</div>
            <div className={days <= 0 ? 'text-status-error' : days <= 30 ? 'text-status-warning' : 'text-text-tertiary'}>
              {days <= 0 ? t('discovery.expired') : `${days}d`}
            </div>
          </div>
        )
      }
    },
    {
      key: 'status', label: t('discovery.columns.status'),
      render: (val) => (
        <Badge
          variant={val === 'managed' ? 'success' : val === 'error' ? 'danger' : 'warning'}
          size="sm"
        >
          {val === 'managed' ? t('discovery.stats.managed')
            : val === 'error' ? t('common.error')
            : t('discovery.stats.unmanaged')}
        </Badge>
      )
    },
    {
      key: 'last_seen', label: t('discovery.columns.lastSeen'),
      render: (val) => val ? <span className="text-xs">{new Date(val).toLocaleString()}</span> : '-'
    },
    ...(isAdmin ? [{
      key: 'id', label: '',
      render: (val) => (
        <Button
          variant="ghost" size="sm" onClick={() => onDelete(val)}
          icon={<Trash size={14} />} className="text-status-error"
        />
      )
    }] : []),
  ]

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select
          value={statusFilter}
          onChange={onStatusFilter}
          options={statusOptions}
          placeholder={t('discovery.filterByStatus')}
          className="w-40"
        />
        {profiles.length > 0 && (
          <Select
            value={profileFilter}
            onChange={onProfileFilter}
            options={[
              { value: '', label: t('common.all') },
              ...profiles.map(p => ({ value: String(p.id), label: p.name }))
            ]}
            placeholder={t('discovery.filterByProfile')}
            className="w-48"
          />
        )}
        <span className="text-sm text-text-secondary ml-auto">{total} {t('common.total')}</span>
        {isAdmin && total > 0 && (
          <Button variant="ghost" size="sm" onClick={onDeleteAll} className="text-status-error">
            <Trash size={14} className="mr-1" /> {t('discovery.deleteAll')}
          </Button>
        )}
      </div>

      {discovered.length === 0 ? (
        <EmptyState
          icon={Globe}
          title={t('discovery.noDiscovered')}
          description={t('discovery.noDiscoveredDescription')}
        />
      ) : (
        <ResponsiveDataTable columns={columns} data={discovered} pageSize={50} />
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════
// History Tab
// ═══════════════════════════════════════════════════
function HistoryTab({ runs, total, t }) {
  const columns = [
    {
      key: 'status', label: t('discovery.columns.status'),
      render: (val) => <RunStatusBadge status={val} />
    },
    {
      key: 'profile_name', label: t('discovery.profile'),
      render: (val) => val || t('discovery.adHocScan')
    },
    {
      key: 'started_at', label: t('discovery.startedAt'),
      sortable: true,
      render: (val) => val ? <span className="text-xs">{new Date(val).toLocaleString()}</span> : '-'
    },
    {
      key: 'completed_at', label: t('discovery.completedAt'),
      render: (val) => val ? <span className="text-xs">{new Date(val).toLocaleString()}</span> : '-'
    },
    { key: 'total_targets', label: t('discovery.targets'), width: 80 },
    { key: 'certs_found', label: t('discovery.certsFound'), width: 100 },
    {
      key: 'new_certs', label: t('common.new'), width: 70,
      render: (val) => val > 0 ? <Badge variant="info" size="sm">+{val}</Badge> : '0'
    },
    {
      key: 'changed_certs', label: t('discovery.changed'), width: 80,
      render: (val) => val > 0 ? <Badge variant="warning" size="sm">{val}</Badge> : '0'
    },
    {
      key: 'triggered_by', label: t('discovery.triggeredBy'),
      render: (val, row) => (
        <span className="text-xs text-text-secondary">
          {val === 'scheduled' ? '⏰' : '👤'} {row.triggered_by_user || val}
        </span>
      )
    },
  ]

  if (runs.length === 0) {
    return (
      <EmptyState
        icon={ClockCounterClockwise}
        title={t('discovery.noHistory')}
        description={t('discovery.noHistoryDescription')}
      />
    )
  }

  return <ResponsiveDataTable columns={columns} data={runs} pageSize={20} />
}

// ═══════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════
function RunStatusBadge({ status }) {
  const map = {
    running: { variant: 'info', icon: ArrowsClockwise },
    completed: { variant: 'success', icon: CheckCircle },
    failed: { variant: 'danger', icon: XCircle },
  }
  const cfg = map[status] || map.completed
  return (
    <Badge variant={cfg.variant} size="sm">
      <cfg.icon size={12} className="mr-1" />
      {status}
    </Badge>
  )
}

function StatCard({ icon: Icon, label, value, color, bgClass }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${bgClass}`}>
          <Icon size={20} weight="duotone" />
        </div>
        <div>
          <div className="text-2xl font-bold">{value}</div>
          <div className="text-xs text-text-secondary">{label}</div>
        </div>
      </div>
    </Card>
  )
}

// ═══════════════════════════════════════════════════
// Profile Form Modal
// ═══════════════════════════════════════════════════
function ProfileFormModal({ profile, onSave, onClose, t }) {
  const [name, setName] = useState(profile?.name || '')
  const [description, setDescription] = useState(profile?.description || '')
  const [targets, setTargets] = useState((profile?.targets || []).join('\n'))
  const [ports, setPorts] = useState((profile?.ports || [443]).join(', '))
  const [scheduleEnabled, setScheduleEnabled] = useState(profile?.schedule_enabled || false)
  const [interval, setInterval] = useState(profile?.schedule_interval_minutes || 1440)
  const [notifyNew, setNotifyNew] = useState(profile?.notify_on_new ?? true)
  const [notifyChange, setNotifyChange] = useState(profile?.notify_on_change ?? true)
  const [notifyExpiry, setNotifyExpiry] = useState(profile?.notify_on_expiry ?? false)

  const handleSubmit = (e) => {
    e.preventDefault()
    const targetsList = targets.split('\n').map(s => s.trim()).filter(Boolean)
    const portsList = ports.split(',').map(s => parseInt(s.trim(), 10)).filter(n => n > 0 && n <= 65535)
    if (!name.trim()) return
    if (targetsList.length === 0) return

    onSave({
      name: name.trim(),
      description: description.trim(),
      targets: targetsList,
      ports: portsList.length > 0 ? portsList : [443],
      schedule_enabled: scheduleEnabled,
      schedule_interval_minutes: interval,
      notify_on_new: notifyNew,
      notify_on_change: notifyChange,
      notify_on_expiry: notifyExpiry,
    })
  }

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={profile ? t('discovery.editProfile') : t('discovery.newProfile')}
    >
      <form onSubmit={handleSubmit} className="p-4 space-y-4">
        <Input
          label={t('common.name')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="Production servers"
        />
        <Input
          label={t('common.description')}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t('discovery.profileDescPlaceholder')}
        />
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1">
            {t('discovery.targets')}
          </label>
          <Textarea
            value={targets}
            onChange={(e) => setTargets(e.target.value)}
            rows={5}
            placeholder={t('discovery.targetsHelp')}
            required
          />
        </div>
        <Input
          label={t('discovery.ports')}
          value={ports}
          onChange={(e) => setPorts(e.target.value)}
          placeholder="443, 8443, 636"
        />

        {/* Schedule */}
        <div className="border-t border-border pt-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={scheduleEnabled}
              onChange={(e) => setScheduleEnabled(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm font-medium">{t('discovery.enableSchedule')}</span>
          </label>
          {scheduleEnabled && (
            <div className="mt-3">
              <Select
                label={t('discovery.scanInterval')}
                value={String(interval)}
                onChange={(v) => setInterval(parseInt(v, 10))}
                options={[
                  { value: '60', label: t('discovery.every1h') },
                  { value: '360', label: t('discovery.every6h') },
                  { value: '720', label: t('discovery.every12h') },
                  { value: '1440', label: t('discovery.every24h') },
                  { value: '10080', label: t('discovery.every7d') },
                ]}
              />
            </div>
          )}
        </div>

        {/* Notifications */}
        <div className="border-t border-border pt-4 space-y-2">
          <span className="text-sm font-medium">{t('discovery.notifications')}</span>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={notifyNew} onChange={(e) => setNotifyNew(e.target.checked)} className="rounded" />
            <span className="text-xs">{t('discovery.notifyOnNew')}</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={notifyChange} onChange={(e) => setNotifyChange(e.target.checked)} className="rounded" />
            <span className="text-xs">{t('discovery.notifyOnChange')}</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={notifyExpiry} onChange={(e) => setNotifyExpiry(e.target.checked)} className="rounded" />
            <span className="text-xs">{t('discovery.notifyOnExpiry')}</span>
          </label>
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit">
            {profile ? t('common.save') : t('common.create')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ═══════════════════════════════════════════════════
// Ad-hoc Scan Modal
// ═══════════════════════════════════════════════════
function AdHocScanModal({ onScan, onClose, t }) {
  const [scanType, setScanType] = useState('targets')
  const [targets, setTargets] = useState('')
  const [subnet, setSubnet] = useState('')
  const [ports, setPorts] = useState('443')

  const handleSubmit = (e) => {
    e.preventDefault()
    const portsList = ports.split(',').map(s => parseInt(s.trim(), 10)).filter(n => n > 0 && n <= 65535)
    if (scanType === 'subnet') {
      if (!subnet.trim()) return
      onScan({ subnet: subnet.trim(), ports: portsList.length > 0 ? portsList : [443] })
    } else {
      const list = targets.split('\n').map(s => s.trim()).filter(Boolean)
      if (list.length === 0) return
      onScan({ targets: list, ports: portsList.length > 0 ? portsList : [443] })
    }
  }

  return (
    <Modal open={true} onClose={onClose} title={t('discovery.quickScan')}>
      <form onSubmit={handleSubmit} className="p-4 space-y-4">
        <Select
          label={t('discovery.scanType')}
          value={scanType}
          onChange={setScanType}
          options={[
            { value: 'targets', label: t('discovery.scanTypeTargets') },
            { value: 'subnet', label: t('discovery.scanTypeSubnet') },
          ]}
        />

        {scanType === 'targets' ? (
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              {t('discovery.targets')}
            </label>
            <Textarea
              value={targets}
              onChange={(e) => setTargets(e.target.value)}
              rows={5}
              placeholder={t('discovery.targetsHelp')}
              required
            />
          </div>
        ) : (
          <Input
            label={t('discovery.subnet')}
            value={subnet}
            onChange={(e) => setSubnet(e.target.value)}
            placeholder={t('discovery.subnetHelp')}
            required
          />
        )}

        <Input
          label={t('discovery.ports')}
          value={ports}
          onChange={(e) => setPorts(e.target.value)}
          placeholder="443, 8443, 636"
        />

        <div className="flex justify-end gap-2 pt-4 border-t border-border">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" icon={<MagnifyingGlass size={16} />}>
            {t('discovery.scan')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
