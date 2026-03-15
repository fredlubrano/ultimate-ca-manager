/**
 * WebSocket Connection Indicator
 * Shows real-time connection status in the UI
 */

import { useWebSocket, ConnectionState } from '../hooks/useWebSocket';
import { WifiHigh, WifiSlash, CircleNotch } from '@phosphor-icons/react';
import { cn } from '../lib/utils';
import { useTranslation } from 'react-i18next';

const stateConfig = {
  [ConnectionState.CONNECTED]: {
    icon: WifiHigh,
    color: 'status-success-text',
    labelKey: 'websocket.status.active',
    pulse: false,
  },
  [ConnectionState.CONNECTING]: {
    icon: CircleNotch,
    color: 'status-warning-text',
    labelKey: 'websocket.status.connecting',
    pulse: true,
  },
  [ConnectionState.DISCONNECTED]: {
    icon: WifiSlash,
    color: 'text-text-tertiary',
    labelKey: 'websocket.status.disabled',
    pulse: false,
  },
  [ConnectionState.ERROR]: {
    icon: WifiSlash,
    color: 'status-danger-text',
    labelKey: 'websocket.status.error',
    pulse: false,
  },
};

export function WebSocketIndicator({ className, showLabel = false, variant = 'default' }) {
  const { connectionState, isConnected, connect } = useWebSocket({ showToasts: false });
  const { t } = useTranslation();
  
  const config = stateConfig[connectionState] || stateConfig[ConnectionState.DISCONNECTED];
  const Icon = config.icon;
  
  const handleClick = () => {
    if (!isConnected) {
      connect();
    }
  };

  // Dot variant — small status dot for embedding in avatars
  // Only visible when connected — no alarming indicators for proxy/Zscaler environments
  if (variant === 'dot') {
    if (!isConnected) return null
    return (
      <span
        title={t(config.labelKey)}
        className={cn('w-2.5 h-2.5 rounded-full border-2 border-bg-secondary bg-status-success', className)}
      />
    )
  }
  
  return (
    <button
      onClick={handleClick}
      title={t(config.labelKey)}
      className={cn(
        'flex items-center gap-1.5 p-1 rounded hover:bg-bg-tertiary transition-colors',
        className
      )}
    >
      <Icon
        size={16}
        weight="bold"
        className={cn(
          config.color,
          config.pulse && 'animate-spin'
        )}
      />
      {showLabel && (
        <span className={cn('text-xs', config.color)}>
          {isConnected ? t('websocket.status.live') : t('websocket.status.offline')}
        </span>
      )}
    </button>
  );
}

export default WebSocketIndicator;
