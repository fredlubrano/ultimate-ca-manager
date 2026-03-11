/**
 * Date Format Store - lightweight global state for date display preferences
 * 
 * Not a React context — works in plain JS utility functions.
 * Set by AuthContext on session verify, read by formatDate utilities.
 * 
 * Formats:
 *   'short'    → "Jan 6, 2026"
 *   'iso'      → "2026-01-06"
 *   'eu'       → "06/01/2026"
 *   'us'       → "01/06/2026"
 *   'long'     → "January 6, 2026"
 */

const VALID_FORMATS = ['short', 'iso', 'eu', 'us', 'long']

let _dateFormat = 'short'
let _showTime = true

export function getDateFormat() {
  return _dateFormat
}

export function setDateFormat(fmt) {
  if (fmt && VALID_FORMATS.includes(fmt)) {
    _dateFormat = fmt
  }
}

export function getShowTime() {
  return _showTime
}

export function setShowTime(show) {
  _showTime = !!show
}

export const DATE_FORMAT_OPTIONS = VALID_FORMATS
