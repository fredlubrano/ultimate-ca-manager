/**
 * Sidebar Component - Mega-menu navigation sidebar
 * Groups: Dashboard (direct), PKI, Protocols, Tools, Governance, Admin
 * Each group icon opens a flyout popover with sub-items
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { 
  House, Certificate, ShieldCheck, FileText, List, User, Key, Gear,
  SignOut, Check, UserCircle, Lightning, ClockCounterClockwise, Robot,
  UsersThree, Shield, Lock, FileX, Vault, Wrench, Globe, CaretRight,
  Gavel, Stamp, ChartBar, Stack, Broadcast
} from '@phosphor-icons/react'
import { Link, useNavigate } from 'react-router-dom'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { usePermission } from '../hooks'
import { cn } from '../lib/utils'
import { Logo } from './Logo'
import { WebSocketIndicator } from './WebSocketIndicator'
import { useMobile } from '../contexts/MobileContext'
import { certificatesService } from '../services'
import { languages } from '../i18n'

// Navigation groups — each has a trigger icon and child items
const navGroups = [
  {
    id: 'pki',
    icon: Certificate,
    labelKey: 'common.navPki',
    children: [
      { id: 'certificates', icon: Certificate, labelKey: 'common.certificates', path: '/certificates' },
      { id: 'cas', icon: ShieldCheck, labelKey: 'common.cas', path: '/cas' },
      { id: 'csrs', icon: FileText, labelKey: 'common.csrs', path: '/csrs' },
      { id: 'templates', icon: List, labelKey: 'common.templates', path: '/templates' },
    ]
  },
  {
    id: 'protocols',
    icon: Broadcast,
    labelKey: 'common.navProtocols',
    children: [
      { id: 'acme', icon: Key, labelKey: 'common.acme', path: '/acme', permission: 'read:acme' },
      { id: 'scep', icon: Robot, labelKey: 'common.scep', path: '/scep-config', permission: 'read:scep' },
      { id: 'est', icon: Globe, labelKey: 'common.est', path: '/est-config', permission: 'read:est' },
      { id: 'crl-ocsp', icon: FileX, labelKey: 'common.crlOcsp', path: '/crl-ocsp', permission: 'read:crl' },
    ]
  },
  {
    id: 'tools',
    icon: Wrench,
    labelKey: 'common.navTools',
    children: [
      { id: 'truststore', icon: Vault, labelKey: 'common.trustStore', path: '/truststore', permission: 'read:truststore' },
      { id: 'operations', icon: Lightning, labelKey: 'common.operations', path: '/operations', adminOnly: true },
      { id: 'tools', icon: Wrench, labelKey: 'common.tools', path: '/tools' },
    ]
  },
  {
    id: 'governance',
    icon: Gavel,
    labelKey: 'common.navGovernance',
    children: [
      { id: 'policies', icon: Gavel, labelKey: 'common.policies', path: '/policies', permission: 'read:policies' },
      { id: 'approvals', icon: Stamp, labelKey: 'common.approvals', path: '/approvals', permission: 'read:approvals' },
      { id: 'reports', icon: ChartBar, labelKey: 'common.reports', path: '/reports', permission: 'read:audit' },
    ]
  },
  {
    id: 'admin',
    icon: Shield,
    labelKey: 'common.navAdmin',
    children: [
      { id: 'users', icon: User, labelKey: 'common.users', path: '/users', adminOnly: true },
      { id: 'rbac', icon: Shield, labelKey: 'common.rbac', path: '/rbac', adminOnly: true },
      { id: 'hsm', icon: Lock, labelKey: 'common.hsm', path: '/hsm', permission: 'read:hsm' },
      { id: 'audit', icon: ClockCounterClockwise, labelKey: 'common.audit', path: '/audit', permission: 'read:audit' },
    ]
  },
]

function NavGroupFlyout({ group, activePage, iconSize, buttonSize, isAdmin, hasPermission, expiringCount, isBadgeDismissed, dismissBadge, t }) {
  const [open, setOpen] = useState(false)
  const timeoutRef = useRef(null)
  const navigate = useNavigate()

  // Filter children by permissions
  const visibleChildren = group.children.filter(child => {
    if (child.adminOnly && !isAdmin()) return false
    if (child.permission && !isAdmin() && !hasPermission(child.permission)) return false
    return true
  })

  if (visibleChildren.length === 0) return null

  const groupHasActive = visibleChildren.some(c => c.id === activePage)
  const GroupIcon = group.icon

  const handleEnter = () => {
    clearTimeout(timeoutRef.current)
    setOpen(true)
  }
  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setOpen(false), 150)
  }

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {/* Trigger icon */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={cn(
          buttonSize,
          "rounded-lg flex items-center justify-center transition-all duration-200 relative group",
          groupHasActive
            ? "sidebar-active-gradient text-accent-primary border border-accent-primary-op20"
            : "text-text-secondary hover:bg-tertiary-op70 hover:text-text-primary"
        )}
        title={t(group.labelKey)}
      >
        <GroupIcon size={iconSize} weight={groupHasActive ? 'fill' : 'regular'} />
        {groupHasActive && (
          <div className="absolute left-0 w-0.5 h-5 bg-accent-primary rounded-r-full" />
        )}
        {/* Expiring badge on PKI group */}
        {group.id === 'pki' && expiringCount > 0 && !isBadgeDismissed && (
          <div
            onClick={dismissBadge}
            className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-status-warning border border-bg-secondary flex items-center justify-center cursor-pointer hover:opacity-70 transition-opacity"
            title={t('common.dismiss')}
          >
            <span className="text-3xs font-bold text-black/80">
              {expiringCount > 9 ? '9+' : expiringCount}
            </span>
          </div>
        )}
        {/* Simple tooltip (hidden when flyout open) */}
        {!open && (
          <div className="absolute left-full ml-2 px-2 py-1 bg-bg-tertiary border border-border rounded-md text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
            {t(group.labelKey)}
          </div>
        )}
      </button>

      {/* Flyout panel */}
      {open && (
        <div
          className="absolute left-full top-0 ml-1.5 z-50 min-w-[180px] py-1.5 bg-bg-secondary border border-border rounded-lg shadow-xl animate-in fade-in slide-in-from-left-2 duration-150"
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          {/* Group header */}
          <div className="px-3 py-1 text-3xs font-semibold text-text-tertiary uppercase tracking-wider">
            {t(group.labelKey)}
          </div>
          {/* Items */}
          {visibleChildren.map(child => {
            const ChildIcon = child.icon
            const isActive = activePage === child.id
            const showBadge = child.id === 'certificates' && expiringCount > 0 && !isBadgeDismissed
            return (
              <Link
                key={child.id}
                to={child.path}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-1.5 mx-1 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-accent-primary-op15 text-accent-primary font-medium"
                    : "text-text-primary hover:bg-bg-tertiary"
                )}
              >
                <ChildIcon size={16} weight={isActive ? 'fill' : 'regular'} />
                <span className="flex-1">{t(child.labelKey)}</span>
                {showBadge && (
                  <span className="text-3xs px-1 py-0.5 rounded-full bg-status-warning text-black/80 font-bold">
                    {expiringCount > 9 ? '9+' : expiringCount}
                  </span>
                )}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function Sidebar({ activePage }) {
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
  const { themeFamily, setThemeFamily, mode, setMode, themes, isLight } = useTheme()
  const { user, logout } = useAuth()
  const { isAdmin, canRead, canWrite, hasPermission } = usePermission()
  const { isLargeScreen } = useMobile()
  
  // Expiring certificates badge
  const [expiringCount, setExpiringCount] = useState(0)
  const [badgeDismissed, setBadgeDismissed] = useState(() => {
    try {
      const stored = localStorage.getItem('ucm_badge_dismissed')
      return stored ? JSON.parse(stored) : { count: 0, at: 0 }
    } catch { return { count: 0, at: 0 } }
  })
  
  const isBadgeDismissed = badgeDismissed.count === expiringCount && expiringCount > 0
  
  const dismissBadge = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    const state = { count: expiringCount, at: Date.now() }
    setBadgeDismissed(state)
    try { localStorage.setItem('ucm_badge_dismissed', JSON.stringify(state)) } catch {}
  }, [expiringCount])
  
  // Load expiring count on mount and periodically
  useEffect(() => {
    const loadExpiringCount = async () => {
      try {
        const stats = await certificatesService.getStats()
        const expiring = stats?.data?.expiring || 0
        const expired = stats?.data?.expired || 0
        setExpiringCount(expiring + expired)
      } catch {
        // Ignore errors
      }
    }
    
    loadExpiringCount()
    const interval = setInterval(loadExpiringCount, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])
  
  // Sizes based on screen width
  const iconSize = isLargeScreen ? 22 : 18
  const buttonSize = isLargeScreen ? 'w-10 h-9' : 'w-8 h-7'
  const sidebarWidth = isLargeScreen ? 'w-[52px]' : 'w-10'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className={cn(sidebarWidth, "h-full border-r border-border-op60 bg-gradient-to-b from-bg-secondary to-bg-tertiary flex flex-col items-center py-2 gap-px")}>
      {/* Logo */}
      <Link to="/" className="flex items-center justify-center mb-2" style={{ width: isLargeScreen ? 42 : 34, height: isLargeScreen ? 42 : 34 }} title={t('common.dashboard')}>
        <Logo variant="icon" withText={false} size={isLargeScreen ? 'sm' : 'xs'} />
      </Link>

      {/* Dashboard - direct link (no flyout) */}
      <Link
        to="/"
        className={cn(
          buttonSize,
          "rounded-lg flex items-center justify-center transition-all duration-200 relative group",
          activePage === ''
            ? "sidebar-active-gradient text-accent-primary border border-accent-primary-op20"
            : "text-text-secondary hover:bg-tertiary-op70 hover:text-text-primary"
        )}
        title={t('common.dashboard')}
      >
        <House size={iconSize} weight={activePage === '' ? 'fill' : 'regular'} />
        {activePage === '' && (
          <div className="absolute left-0 w-0.5 h-5 bg-accent-primary rounded-r-full" />
        )}
        <div className="absolute left-full ml-2 px-2 py-1 bg-bg-tertiary border border-border rounded-md text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
          {t('common.dashboard')}
        </div>
      </Link>

      <div className="w-6 h-px bg-border-op40 my-2" />

      {/* Nav groups with flyout menus */}
      {navGroups.map(group => (
        <NavGroupFlyout
          key={group.id}
          group={group}
          activePage={activePage}
          iconSize={iconSize}
          buttonSize={buttonSize}
          isAdmin={isAdmin}
          hasPermission={hasPermission}
          expiringCount={expiringCount}
          isBadgeDismissed={isBadgeDismissed}
          dismissBadge={dismissBadge}
          t={t}
        />
      ))}

      <div className="flex-1" />

      {/* Settings - admin/operator only */}
      {(isAdmin() || canRead('settings')) && (
      <Link
        to="/settings"
        className={cn(
          buttonSize,
          "rounded-lg flex items-center justify-center transition-all duration-200 relative group",
          activePage === 'settings'
            ? "sidebar-active-gradient text-accent-primary border border-accent-primary-op20"
            : "text-text-secondary hover:bg-tertiary-op70 hover:text-text-primary"
        )}
        title={t('common.settings')}
      >
        <Gear size={iconSize} weight={activePage === 'settings' ? 'fill' : 'regular'} />
        {activePage === 'settings' && (
          <div className="absolute left-0 w-0.5 h-5 bg-accent-primary rounded-r-full" />
        )}
        <div className="absolute left-full ml-2 px-2 py-1 bg-bg-tertiary border border-border rounded-md text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
          {t('common.settings')}
        </div>
      </Link>
      )}

      {/* WebSocket Indicator */}
      <WebSocketIndicator className="mx-auto" />

      {/* User Menu (with Theme) */}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className={cn(buttonSize, "rounded-sm bg-accent-primary-op10 border border-accent-primary-op20 flex items-center justify-center text-accent-primary hover:bg-accent-primary-op20 transition-all group")}>
            <UserCircle size={iconSize} weight="bold" />
            <div className="absolute left-full ml-2 px-2 py-1 bg-bg-tertiary border border-border rounded-sm text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
              {user?.username || 'User'}
            </div>
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content 
            className="min-w-[200px] bg-bg-secondary border border-border rounded-sm shadow-lg p-1 z-50"
            sideOffset={5}
            side="right"
          >
            {/* User identity header */}
            <div className="px-3 py-2 mb-1">
              <div className="text-sm font-semibold text-text-primary truncate">{user?.username || 'User'}</div>
              <div className="text-xs text-text-tertiary capitalize">{user?.role || ''}</div>
            </div>
            <DropdownMenu.Separator className="h-px bg-border mb-1" />

            <DropdownMenu.Item
              onClick={() => navigate('/account')}
              className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors"
            >
              <UserCircle size={16} />
              <span>{t('common.account')}</span>
            </DropdownMenu.Item>

            {(isAdmin() || canRead('settings')) && (
            <DropdownMenu.Item
              onClick={() => navigate('/settings')}
              className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors"
            >
              <Gear size={16} />
              <span>{t('common.settings')}</span>
            </DropdownMenu.Item>
            )}

            <DropdownMenu.Separator className="h-px bg-border my-1" />

            {/* Theme sub-section */}
            <DropdownMenu.Label className="px-3 py-1.5 text-xs text-text-tertiary uppercase tracking-wider">
              {t('settings.colorTheme')}
            </DropdownMenu.Label>
            {themes.map(theme => (
              <DropdownMenu.Item
                key={theme.id}
                onClick={() => setThemeFamily(theme.id)}
                className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors"
              >
                <div 
                  className="w-3 h-3 rounded-full border border-border"
                  style={{ background: theme.accent }}
                />
                <span className="flex-1">{theme.name}</span>
                {themeFamily === theme.id && (
                  <Check size={16} weight="bold" className="text-accent-primary" />
                )}
              </DropdownMenu.Item>
            ))}
            
            <DropdownMenu.Separator className="h-px bg-border my-1" />
            
            <DropdownMenu.Label className="px-3 py-1.5 text-xs text-text-tertiary uppercase tracking-wider">
              {t('settings.appearanceMode')}
            </DropdownMenu.Label>
            {[
              { id: 'system', labelKey: 'settings.followSystem' },
              { id: 'dark', labelKey: 'settings.dark' },
              { id: 'light', labelKey: 'settings.light' }
            ].map(opt => (
              <DropdownMenu.Item
                key={opt.id}
                onClick={() => setMode(opt.id)}
                className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors"
              >
                <span className="flex-1">{t(opt.labelKey)}</span>
                {mode === opt.id && (
                  <Check size={16} weight="bold" className="text-accent-primary" />
                )}
              </DropdownMenu.Item>
            ))}

            <DropdownMenu.Separator className="h-px bg-border my-1" />

            {/* Language sub-section */}
            <DropdownMenu.Label className="px-3 py-1.5 text-xs text-text-tertiary uppercase tracking-wider">
              {t('settings.language')}
            </DropdownMenu.Label>
            <DropdownMenu.Sub>
              <DropdownMenu.SubTrigger className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors data-[state=open]:bg-bg-tertiary">
                <Globe size={16} />
                <span className="flex-1">{languages.find(l => l.code === (i18n.language?.split('-')[0] || 'en'))?.flag} {languages.find(l => l.code === (i18n.language?.split('-')[0] || 'en'))?.name || 'English'}</span>
                <CaretRight size={12} className="text-text-tertiary" />
              </DropdownMenu.SubTrigger>
              <DropdownMenu.Portal>
                <DropdownMenu.SubContent className="min-w-[180px] bg-bg-secondary border border-border rounded-sm shadow-lg p-1 z-50">
                  {languages.map(lang => (
                    <DropdownMenu.Item
                      key={lang.code}
                      onClick={() => {
                        i18n.changeLanguage(lang.code)
                        try { localStorage.setItem('i18nextLng', lang.code) } catch {}
                      }}
                      className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:bg-bg-tertiary text-text-primary transition-colors"
                    >
                      <span>{lang.flag}</span>
                      <span className="flex-1">{lang.name}</span>
                      {(i18n.language?.split('-')[0] || 'en') === lang.code && (
                        <Check size={16} weight="bold" className="text-accent-primary" />
                      )}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.SubContent>
              </DropdownMenu.Portal>
            </DropdownMenu.Sub>

            <DropdownMenu.Separator className="h-px bg-border my-1" />

            <DropdownMenu.Item
              onClick={handleLogout}
              className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm cursor-pointer outline-none hover:status-danger-bg status-danger-text transition-colors"
            >
              <SignOut size={16} />
              <span>{t('auth.logout')}</span>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  )
}

// Export navGroups for use by AppShell mobile nav
export { navGroups }
