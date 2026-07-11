// Local mock backend for UX/design review sessions — NOT used in production
// or automated tests. Runs as a Vite dev-server middleware (same origin,
// same port as the frontend), so `npm run dev:mock` is the only command
// needed. See frontend/mock/README.md.
import { randomUUID } from 'node:crypto'
import { state, CURRENT_USER, findUser } from './data.js'

const ARTIFICIAL_DELAY_MS = 200 // makes loading states visible for design review

// ---------------------------------------------------------------------------
// Tiny router: routes are tried in registration order, so register more
// specific literal paths (…/checks/bulk/pause) before the generic
// param-based ones they'd otherwise collide with (…/checks/:checkId/pause).
// ---------------------------------------------------------------------------
const routes = []

function route(method, pattern, handler) {
  const paramNames = []
  const regexSource = pattern
    .split('/')
    .map((segment) => {
      if (segment.startsWith(':')) {
        paramNames.push(segment.slice(1))
        return '([^/]+)'
      }
      return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    })
    .join('/')
  const regex = new RegExp(`^${regexSource}$`)
  routes.push({ method, regex, paramNames, handler })
}

function match(method, pathname) {
  for (const r of routes) {
    if (r.method !== method) continue
    const m = r.regex.exec(pathname)
    if (!m) continue
    const params = {}
    r.paramNames.forEach((name, i) => { params[name] = decodeURIComponent(m[i + 1]) })
    return { handler: r.handler, params }
  }
  return null
}

class HttpError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function notFound(what = 'Resource') {
  return new HttpError(404, `${what} not found`)
}

// ---------------------------------------------------------------------------
// Helpers over the seed data
// ---------------------------------------------------------------------------
function teamRole(teamId) {
  return state.membership[teamId] || null
}

function requireTeam(teamId) {
  const team = state.teams.find((t) => t.teamId === teamId)
  if (!team) throw notFound('Team')
  return team
}

function requireCheck(teamId, checkId) {
  const check = (state.checks[teamId] || []).find((c) => c.checkId === checkId)
  if (!check) throw notFound('Check')
  return check
}

function checksList(teamId) {
  return state.checks[teamId] || []
}

function aggregateStats(pings) {
  const successCount = pings.filter((p) => p.pingType === 'success').length
  const failCount = pings.filter((p) => p.pingType === 'fail').length
  const totalPings = successCount + failCount
  const samples = pings.filter((p) => p.responseTimeMs != null).map((p) => p.responseTimeMs)
  const sorted = [...samples].sort((a, b) => a - b)
  const pct = (p) => (sorted.length ? sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)] : null)
  const series = [...pings].reverse().filter((p) => p.responseTimeMs != null).map((p) => ({
    timestamp: p.receivedAt, responseTimeMs: p.responseTimeMs, pingType: p.pingType,
  }))
  return {
    uptimePct: totalPings ? Math.round((successCount / totalPings) * 10000) / 100 : 0,
    totalPings, successCount, failCount,
    avgResponseMs: samples.length ? Math.round(samples.reduce((a, b) => a + b, 0) / samples.length) : null,
    p95ResponseMs: pct(95),
    maxResponseMs: sorted.length ? sorted[sorted.length - 1] : null,
    minResponseMs: sorted.length ? sorted[0] : null,
    latestResponseMs: series.length ? series[series.length - 1].responseTimeMs : null,
    responseTimeSeries: series,
  }
}

function aggregateErrors(pings) {
  const failures = pings.filter((p) => p.pingType === 'fail')
  const codeCounts = {}
  for (const f of failures) {
    const code = f.code || 'unknown'
    codeCounts[code] = (codeCounts[code] || 0) + 1
  }
  const failureCodes = Object.entries(codeCounts).map(([code, count]) => ({ code, count }))
  const mostCommon = failureCodes.sort((a, b) => b.count - a.count)[0]
  return {
    totalFailures: failures.length,
    mostCommonCode: mostCommon ? mostCommon.code : null,
    lastFailureAt: failures.length ? failures[0].receivedAt : null,
    longestIncident: failures.length ? {
      startedAt: failures[failures.length - 1].receivedAt,
      endedAt: failures[0].receivedAt,
      durationSeconds: 900,
      failureCount: failures.length,
      dominantCode: mostCommon ? mostCommon.code : 'unknown',
    } : null,
    failureCodes,
    recentFailures: failures.slice(0, 10),
  }
}

function aggregateUptime(check, excludeMaintenance) {
  const pings = state.pings[check.checkId] || []
  const stats = aggregateStats(pings)
  const downtimeMinutes = stats.failCount * 5
  return {
    from: new Date(Date.now() - 7 * 86400000).toISOString(),
    to: new Date().toISOString(),
    excludeMaintenance,
    uptimePct: stats.uptimePct,
    totalObservedMinutes: 7 * 24 * 60,
    downtimeMinutes,
    excludedMaintenanceMinutes: excludeMaintenance ? 60 : 0,
    incidents: stats.failCount ? [{
      startedAt: pings.find((p) => p.pingType === 'fail')?.receivedAt || new Date().toISOString(),
      endedAt: new Date().toISOString(),
      durationSeconds: downtimeMinutes * 60,
      failureCount: stats.failCount,
      dominantCode: '503',
    }] : [],
    maintenanceWindows: state.maintenanceWindows[check.teamId] || [],
  }
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------
route('GET', '/me', () => CURRENT_USER)

route('POST', '/teams', (_p, body) => {
  const teamId = `team-${randomUUID().slice(0, 8)}`
  const team = { teamId, name: body.name, slug: body.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'), createdAt: new Date().toISOString(), createdBy: CURRENT_USER.userId }
  state.teams.push(team)
  state.membership[teamId] = 'admin'
  state.checks[teamId] = []
  state.channels[teamId] = []
  state.members[teamId] = [{ userId: CURRENT_USER.userId, email: CURRENT_USER.email, name: CURRENT_USER.name, role: 'admin', joinedAt: team.createdAt, status: 'active' }]
  state.auditLog[teamId] = []
  state.maintenanceWindows[teamId] = []
  state.reports[teamId] = []
  state.apiTokens[teamId] = []
  return { ...team, role: 'admin' }
})

route('GET', '/teams', () => state.teams
  .filter((t) => teamRole(t.teamId))
  .map((t) => ({ teamId: t.teamId, name: t.name, slug: t.slug, role: teamRole(t.teamId), createdAt: t.createdAt })))

route('GET', '/teams/:teamId', ({ teamId }) => {
  const team = requireTeam(teamId)
  return { teamId: team.teamId, name: team.name, slug: team.slug, createdAt: team.createdAt, createdBy: team.createdBy }
})

route('PATCH', '/teams/:teamId', ({ teamId }, body) => {
  const team = requireTeam(teamId)
  if (body.name) team.name = body.name
  return team
})

route('DELETE', '/teams/:teamId', ({ teamId }) => {
  state.teams = state.teams.filter((t) => t.teamId !== teamId)
  delete state.membership[teamId]
  return { message: 'Team deleted' }
})

// --- Checks -----------------------------------------------------------------

route('GET', '/teams/:teamId/checks', ({ teamId }) => checksList(teamId))

route('POST', '/teams/:teamId/checks', ({ teamId }, body) => {
  requireTeam(teamId)
  const checkId = `check-${randomUUID().slice(0, 8)}`
  const check = {
    checkId, teamId, name: body.name, slug: body.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    token: `tok_${randomUUID().replace(/-/g, '')}`,
    status: 'pending', type: body.type || 'heartbeat',
    schedule: body.schedule || null, periodSeconds: body.periodSeconds || null, graceSeconds: body.graceSeconds ?? 300,
    lastPingAt: null, nextDueAt: null, alertAfterAt: null, lastAlertAt: null,
    createdAt: new Date().toISOString(),
    alertChannels: body.alertChannels || [], tags: body.tags || [],
    escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
    suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
    url: body.url || null, expectedStatusCode: body.expectedStatusCode ?? 200,
    expectedString: body.expectedString || null, failureThreshold: body.failureThreshold ?? 1,
  }
  state.checks[teamId] = state.checks[teamId] || []
  state.checks[teamId].push(check)
  state.pings[checkId] = []
  state.alertHistory[checkId] = []
  return check
})

route('POST', '/teams/:teamId/checks/bulk/pause', ({ teamId }, body) => {
  for (const id of body.check_ids || []) {
    const c = checksList(teamId).find((c) => c.checkId === id)
    if (c) c.status = 'paused'
  }
  return { message: `${(body.check_ids || []).length} check(s) paused` }
})

route('POST', '/teams/:teamId/checks/bulk/resume', ({ teamId }, body) => {
  for (const id of body.check_ids || []) {
    const c = checksList(teamId).find((c) => c.checkId === id)
    if (c) c.status = 'up'
  }
  return { message: `${(body.check_ids || []).length} check(s) resumed` }
})

route('GET', '/teams/:teamId/checks/:checkId', ({ teamId, checkId }) => requireCheck(teamId, checkId))

route('PATCH', '/teams/:teamId/checks/:checkId', ({ teamId, checkId }, body) => {
  const check = requireCheck(teamId, checkId)
  Object.assign(check, body)
  return check
})

route('POST', '/teams/:teamId/checks/:checkId/pause', ({ teamId, checkId }) => {
  requireCheck(teamId, checkId).status = 'paused'
  return { message: 'Check paused' }
})

route('POST', '/teams/:teamId/checks/:checkId/resume', ({ teamId, checkId }) => {
  requireCheck(teamId, checkId).status = 'up'
  return { message: 'Check resumed' }
})

route('POST', '/teams/:teamId/checks/:checkId/rotate-token', ({ teamId, checkId }) => {
  const check = requireCheck(teamId, checkId)
  check.token = `tok_${randomUUID().replace(/-/g, '')}`
  return check
})

route('POST', '/teams/:teamId/checks/:checkId/escalate', ({ teamId, checkId }) => {
  requireCheck(teamId, checkId).escalationTriggeredAt = new Date().toISOString()
  return { message: 'Escalation triggered successfully' }
})

route('POST', '/teams/:teamId/checks/:checkId/suppress', ({ teamId, checkId }) => {
  const check = requireCheck(teamId, checkId)
  check.suppressedUntil = new Date(Date.now() + (check.suppressDurationMinutes || 60) * 60000).toISOString()
  return { message: `Alerts suppressed for ${check.suppressDurationMinutes || 60} minutes` }
})

route('DELETE', '/teams/:teamId/checks/:checkId', ({ teamId, checkId }) => {
  state.checks[teamId] = checksList(teamId).filter((c) => c.checkId !== checkId)
  return { message: 'Check deleted successfully' }
})

route('GET', '/teams/:teamId/checks/:checkId/pings', ({ teamId, checkId }, _body, query) => {
  requireCheck(teamId, checkId)
  const limit = parseInt(query.get('limit') || '20', 10)
  return (state.pings[checkId] || []).slice(0, limit)
})

route('GET', '/teams/:teamId/checks/:checkId/stats', ({ teamId, checkId }, _body, query) => {
  requireCheck(teamId, checkId)
  return { period: query.get('range') || '24h', ...aggregateStats(state.pings[checkId] || []) }
})

route('GET', '/teams/:teamId/checks/:checkId/errors/summary', ({ teamId, checkId }, _body, query) => {
  requireCheck(teamId, checkId)
  return { period: query.get('range') || '24h', ...aggregateErrors(state.pings[checkId] || []) }
})

route('GET', '/teams/:teamId/checks/:checkId/uptime', ({ teamId, checkId }, _body, query) => {
  const check = requireCheck(teamId, checkId)
  return aggregateUptime(check, query.get('exclude_maintenance') !== 'false')
})

route('GET', '/teams/:teamId/checks/:checkId/alert-history', ({ teamId, checkId }, _body, query) => {
  requireCheck(teamId, checkId)
  const limit = parseInt(query.get('limit') || '50', 10)
  return (state.alertHistory[checkId] || []).slice(0, limit)
})

// --- Audit --------------------------------------------------------------

route('GET', '/teams/:teamId/audit', ({ teamId }, _body, query) => {
  const limit = parseInt(query.get('limit') || '100', 10)
  return (state.auditLog[teamId] || []).slice(0, limit)
})

// --- Maintenance windows --------------------------------------------------

route('GET', '/teams/:teamId/maintenance', ({ teamId }, _body, query) => {
  const checkId = query.get('check_id')
  const windows = state.maintenanceWindows[teamId] || []
  return checkId ? windows.filter((w) => !w.checkId || w.checkId === checkId) : windows
})

route('POST', '/teams/:teamId/maintenance', ({ teamId }, body) => {
  const window = {
    windowId: `maint-${randomUUID().slice(0, 8)}`, teamId,
    checkId: body.checkId || body.check_id || null,
    startAt: body.startAt || body.start_at, endAt: body.endAt || body.end_at,
    label: body.label || null, createdBy: CURRENT_USER.userId, createdAt: new Date().toISOString(),
  }
  state.maintenanceWindows[teamId] = state.maintenanceWindows[teamId] || []
  state.maintenanceWindows[teamId].push(window)
  return window
})

route('DELETE', '/teams/:teamId/maintenance/:windowId', ({ teamId, windowId }) => {
  state.maintenanceWindows[teamId] = (state.maintenanceWindows[teamId] || []).filter((w) => w.windowId !== windowId)
  return { message: 'Maintenance window deleted' }
})

// --- Reports ---------------------------------------------------------------

route('POST', '/teams/:teamId/reports', ({ teamId }, body) => {
  const reportId = `report-${randomUUID().slice(0, 8)}`
  const report = {
    reportId, teamId, checkId: body.checkId || null, reportType: body.reportType, format: body.format,
    from: body.from, to: body.to, status: 'completed',
    downloadUrl: `/teams/${teamId}/reports/${reportId}/download`,
    createdAt: new Date().toISOString(), createdBy: CURRENT_USER.userId,
    expiresAt: new Date(Date.now() + 7 * 86400000).toISOString(),
    fileName: `${body.reportType}-report-${reportId}.${body.format}`, contentType: body.format === 'csv' ? 'text/csv' : 'application/json',
  }
  state.reports[teamId] = state.reports[teamId] || []
  state.reports[teamId].push(report)
  return report
})

route('GET', '/teams/:teamId/reports', ({ teamId }) => state.reports[teamId] || [])

route('GET', '/teams/:teamId/reports/:reportId', ({ teamId, reportId }) => {
  const report = (state.reports[teamId] || []).find((r) => r.reportId === reportId)
  if (!report) throw notFound('Report')
  return report
})

route('DELETE', '/teams/:teamId/reports/:reportId', ({ teamId, reportId }) => {
  state.reports[teamId] = (state.reports[teamId] || []).filter((r) => r.reportId !== reportId)
  return { message: 'Report deleted' }
})

route('GET', '/teams/:teamId/reports/:reportId/download', ({ teamId, reportId }) => {
  const report = (state.reports[teamId] || []).find((r) => r.reportId === reportId)
  if (!report) throw notFound('Report')
  const body = report.contentType === 'text/csv'
    ? 'check_id,check_name,status\ncheck-2,api-health-poll,late\n'
    : JSON.stringify({ teamId, reportType: report.reportType, generatedAt: report.createdAt }, null, 2)
  return { __raw: true, body, contentType: report.contentType, fileName: report.fileName }
})

// --- Members / invitations --------------------------------------------------

route('GET', '/teams/:teamId/members', ({ teamId }) => state.members[teamId] || [])

route('POST', '/teams/:teamId/members', ({ teamId }, body) => {
  state.members[teamId] = state.members[teamId] || []
  state.members[teamId].push({ userId: null, email: body.email, name: 'Pending User', role: body.role || 'member', joinedAt: new Date().toISOString(), status: 'pending' })
  return { message: `Invitation sent to ${body.email}` }
})

route('DELETE', '/teams/:teamId/members/:userId', ({ teamId, userId }) => {
  state.members[teamId] = (state.members[teamId] || []).filter((m) => m.userId !== userId)
  return { message: 'Member removed successfully' }
})

route('PATCH', '/teams/:teamId/members/:userId', ({ teamId, userId }, body) => {
  const member = (state.members[teamId] || []).find((m) => m.userId === userId)
  if (member) member.role = body.role
  return { message: 'Member role updated successfully' }
})

route('DELETE', '/teams/:teamId/invitations/:email', ({ teamId, email }) => {
  state.members[teamId] = (state.members[teamId] || []).filter((m) => m.email !== email)
  return { message: 'Invitation deleted' }
})

// --- Alert channels ----------------------------------------------------------

route('GET', '/teams/:teamId/channels', ({ teamId }) => state.channels[teamId] || [])

route('POST', '/teams/:teamId/channels', ({ teamId }, body) => {
  const channel = {
    channelId: `chan-${randomUUID().slice(0, 8)}`, teamId,
    name: body.name, displayName: body.displayName, type: body.type,
    configuration: body.configuration || {}, shared: !!body.shared,
    createdAt: new Date().toISOString(), createdBy: CURRENT_USER.userId,
  }
  state.channels[teamId] = state.channels[teamId] || []
  state.channels[teamId].push(channel)
  return channel
})

route('GET', '/teams/:teamId/channels/:channelId', ({ teamId, channelId }) => {
  const channel = (state.channels[teamId] || []).find((c) => c.channelId === channelId)
  if (!channel) throw notFound('Alert channel')
  return channel
})

route('PATCH', '/teams/:teamId/channels/:channelId', ({ teamId, channelId }, body) => {
  const channel = (state.channels[teamId] || []).find((c) => c.channelId === channelId)
  if (!channel) throw notFound('Alert channel')
  if (body.displayName) channel.displayName = body.displayName
  if (body.configuration) channel.configuration = body.configuration
  if (typeof body.shared === 'boolean') channel.shared = body.shared
  return channel
})

route('DELETE', '/teams/:teamId/channels/:channelId', ({ teamId, channelId }) => {
  state.channels[teamId] = (state.channels[teamId] || []).filter((c) => c.channelId !== channelId)
  return { message: 'Alert channel deleted successfully' }
})

route('POST', '/teams/:teamId/channels/:channelId/test', () => ({ message: 'Test notification sent successfully' }))

// --- API tokens ---------------------------------------------------------

route('GET', '/teams/:teamId/api-tokens', ({ teamId }) => state.apiTokens[teamId] || [])

route('POST', '/teams/:teamId/api-tokens', ({ teamId }, body) => {
  const token = {
    token_id: `apitok-${randomUUID().slice(0, 8)}`, name: body.name,
    created_at: new Date().toISOString(), last_used_at: null, expires_at: body.expires_at || null,
    user_id: CURRENT_USER.userId,
  }
  state.apiTokens[teamId] = state.apiTokens[teamId] || []
  state.apiTokens[teamId].push(token)
  return { ...token, token: `pc_${randomUUID().replace(/-/g, '')}` }
})

route('DELETE', '/teams/:teamId/api-tokens/:tokenId', ({ teamId, tokenId }) => {
  state.apiTokens[teamId] = (state.apiTokens[teamId] || []).filter((t) => t.token_id !== tokenId)
  return { deleted: true, token_id: tokenId }
})

// ---------------------------------------------------------------------------
// Vite plugin
// ---------------------------------------------------------------------------
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf-8')
      if (!raw) return resolve({})
      try {
        resolve(JSON.parse(raw))
      } catch (e) {
        reject(new HttpError(400, 'Invalid JSON body'))
      }
    })
    req.on('error', reject)
  })
}

export function mockApiPlugin() {
  return {
    name: 'pulsechecks-mock-api',
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        // Let real page navigations (full loads/refreshes) fall through to
        // Vite's SPA handling instead of being treated as API calls — some
        // page routes and API routes share the same /teams/:id/... shape.
        if ((req.headers.accept || '').includes('text/html')) return next()

        const url = new URL(req.url, 'http://localhost')
        const found = match(req.method, url.pathname)
        if (!found) return next()

        try {
          const body = ['POST', 'PATCH', 'PUT', 'DELETE'].includes(req.method) ? await readBody(req) : {}
          if (ARTIFICIAL_DELAY_MS) await new Promise((r) => setTimeout(r, ARTIFICIAL_DELAY_MS))
          const result = found.handler(found.params, body, url.searchParams)

          if (result && result.__raw) {
            res.statusCode = 200
            res.setHeader('Content-Type', result.contentType)
            res.setHeader('Content-Disposition', `attachment; filename="${result.fileName}"`)
            res.end(result.body)
            return
          }

          res.statusCode = 200
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(result ?? null))
        } catch (err) {
          const status = err instanceof HttpError ? err.status : 500
          res.statusCode = status
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ error: err.message || 'Mock server error' }))
          if (status === 500) console.error('[mock-api]', err)
        }
      })
      console.log('\n  \x1b[35m➜\x1b[0m  \x1b[1mMock API active\x1b[0m — serving fixture data, no backend required\n')
    },
  }
}
