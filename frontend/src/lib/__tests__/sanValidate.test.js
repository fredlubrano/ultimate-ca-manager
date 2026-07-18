import { describe, it, expect } from 'vitest'
import { getAutoSansFromCn, getSanValidationError, isCnEmail, isCnHostname } from '../sanValidate'

describe('sanValidate CN auto-SAN', () => {
  it('does not treat email CN as DNS on server cert', () => {
    expect(getAutoSansFromCn({ cn: 'fred@fred.fr', certType: 'server' })).toEqual([])
  })

  it('adds email SAN for email cert type', () => {
    expect(getAutoSansFromCn({ cn: 'fred@fred.fr', certType: 'email' })).toEqual([
      { type: 'email', value: 'fred@fred.fr' },
    ])
  })

  it('adds DNS SAN for hostname CN on server cert', () => {
    expect(getAutoSansFromCn({ cn: 'www.example.com', certType: 'server' })).toEqual([
      { type: 'dns', value: 'www.example.com' },
    ])
  })

  it('adds IP SAN for IP CN on server cert', () => {
    expect(getAutoSansFromCn({ cn: '10.0.0.1', certType: 'server' })).toEqual([
      { type: 'ip', value: '10.0.0.1' },
    ])
  })

  it('classifies email vs hostname', () => {
    expect(isCnEmail('fred@fred.fr')).toBe(true)
    expect(isCnHostname('fred@fred.fr')).toBe(false)
    expect(isCnHostname('www.example.com')).toBe(true)
  })

  it('uses certificates i18n namespace when requested', () => {
    const err = getSanValidationError('ip', 'www.example.com', { i18nNs: 'certificates' })
    expect(err?.key).toBe('certificates.sanFqdnUseDns')
  })

  it('accepts authority-less URIs like the backend (urn:, mailto:, did:)', () => {
    expect(getSanValidationError('uri', 'urn:uuid:6e8bc430-9c3a-11d9-9669-0800200c9a66')).toBeNull()
    expect(getSanValidationError('uri', 'mailto:admin@example.com')).toBeNull()
    expect(getSanValidationError('uri', 'did:example:123')).toBeNull()
    expect(getSanValidationError('uri', 'https://example.com/acme')).toBeNull()
  })

  it('still rejects a URI with no scheme', () => {
    const err = getSanValidationError('uri', 'not-a-uri')
    expect(err?.key).toBe('csrs.sanUriInvalid')
  })
})
