// Seed data for the local mock backend (design/UX sandbox only).
// Deliberately covers every status/edge case the UI needs to render:
// late checks, zero-channel checks, suppressed checks, pending checks,
// retrying/failed alert deliveries, long ping history, etc.

const HOUR = 3600
const now = () => Math.floor(Date.now() / 1000)
const iso = (secondsAgo = 0) => new Date((now() - secondsAgo) * 1000).toISOString()
const isoFuture = (secondsAhead = 0) => new Date((now() + secondsAhead) * 1000).toISOString()

export const CURRENT_USER = {
  userId: 'user-demo-1',
  email: 'jordan@example.com',
  name: 'Jordan Alvarez',
  createdAt: iso(60 * 86400),
  lastLoginAt: iso(60),
}

const OTHER_USERS = [
  { userId: 'user-demo-2', email: 'priya@example.com', name: 'Priya Nandakumar' },
  { userId: 'user-demo-3', email: 'marcus@example.com', name: 'Marcus Webb' },
  { userId: 'user-demo-4', email: 'sam@example.com', name: 'Sam Okafor' },
]

export const state = {
  teams: [
    { teamId: 'team-sre', name: 'Platform SRE', slug: 'platform-sre', createdAt: iso(200 * 86400), createdBy: CURRENT_USER.userId },
    { teamId: 'team-data', name: 'Data Engineering', slug: 'data-engineering', createdAt: iso(120 * 86400), createdBy: 'user-demo-2' },
  ],

  // teamId -> role for the current user
  membership: {
    'team-sre': 'admin',
    'team-data': 'member',
  },

  members: {
    'team-sre': [
      { userId: CURRENT_USER.userId, email: CURRENT_USER.email, name: CURRENT_USER.name, role: 'admin', joinedAt: iso(200 * 86400), status: 'active' },
      { userId: 'user-demo-2', email: 'priya@example.com', name: 'Priya Nandakumar', role: 'admin', joinedAt: iso(190 * 86400), status: 'active' },
      { userId: 'user-demo-3', email: 'marcus@example.com', name: 'Marcus Webb', role: 'member', joinedAt: iso(90 * 86400), status: 'active' },
      { userId: null, email: 'new-hire@example.com', name: 'Pending User', role: 'member', joinedAt: iso(2 * 86400), status: 'pending' },
    ],
    'team-data': [
      { userId: 'user-demo-2', email: 'priya@example.com', name: 'Priya Nandakumar', role: 'admin', joinedAt: iso(120 * 86400), status: 'active' },
      { userId: CURRENT_USER.userId, email: CURRENT_USER.email, name: CURRENT_USER.name, role: 'member', joinedAt: iso(45 * 86400), status: 'active' },
      { userId: 'user-demo-4', email: 'sam@example.com', name: 'Sam Okafor', role: 'member', joinedAt: iso(45 * 86400), status: 'active' },
    ],
  },

  channels: {
    'team-sre': [
      {
        channelId: 'chan-mattermost-1', teamId: 'team-sre', name: 'platform-oncall',
        displayName: 'Platform Oncall (Mattermost)', type: 'mattermost',
        configuration: { webhook_url: 'https://chat.example.com/hooks/abc123' },
        shared: false, createdAt: iso(180 * 86400), createdBy: CURRENT_USER.userId,
      },
      {
        channelId: 'chan-webhook-1', teamId: 'team-sre', name: 'pagerduty-bridge',
        displayName: 'PagerDuty Bridge', type: 'webhook',
        configuration: { webhook_url: 'https://events.pagerduty.com/integration/xyz/enqueue' },
        shared: false, createdAt: iso(150 * 86400), createdBy: 'user-demo-2',
      },
      {
        channelId: 'chan-email-1', teamId: 'team-sre', name: 'sre-distro',
        displayName: 'SRE Distro (Email)', type: 'email',
        configuration: { recipients: ['sre-oncall@example.com', 'jordan@example.com'] },
        shared: false, createdAt: iso(100 * 86400), createdBy: CURRENT_USER.userId,
      },
      {
        channelId: 'chan-telegram-1', teamId: 'team-sre', name: 'mobile-alerts',
        displayName: 'Mobile Alerts', type: 'telegram',
        configuration: { bot_token: '123456789:AAExampleBotTokenNotReal', chat_id: '-1001234567890' },
        shared: false, createdAt: iso(60 * 86400), createdBy: 'user-demo-3',
      },
      {
        channelId: 'chan-shared-1', teamId: 'team-sre', name: 'company-incidents',
        displayName: 'Company-wide Incidents', type: 'mattermost',
        configuration: { webhook_url: 'https://chat.example.com/hooks/shared456' },
        shared: true, createdAt: iso(170 * 86400), createdBy: CURRENT_USER.userId,
      },
    ],
    'team-data': [
      {
        channelId: 'chan-data-webhook', teamId: 'team-data', name: 'data-eng-webhook',
        displayName: 'Data Eng Webhook', type: 'webhook',
        configuration: { webhook_url: 'https://hooks.example.com/data-eng' },
        shared: false, createdAt: iso(90 * 86400), createdBy: 'user-demo-2',
      },
    ],
  },

  checks: {
    'team-sre': [
      {
        checkId: 'check-1', teamId: 'team-sre', name: 'nightly-db-backup', slug: 'nightly-db-backup',
        token: 'tok_demo_nightlydbbackup01', status: 'up', type: 'cron', schedule: '0 2 * * *',
        periodSeconds: null, graceSeconds: 3600,
        lastPingAt: iso(6 * HOUR), nextDueAt: String(now() + 18 * HOUR), alertAfterAt: String(now() + 19 * HOUR), lastAlertAt: null,
        createdAt: iso(180 * 86400),
        alertChannels: ['chan-mattermost-1', 'chan-email-1'],
        tags: ['prod', 'db'],
        escalationMinutes: 30, escalationAlertChannels: ['chan-webhook-1'], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-2', teamId: 'team-sre', name: 'api-health-poll', slug: 'api-health-poll',
        token: 'tok_demo_apihealthpoll02', status: 'late', type: 'http',
        url: 'https://api.example.com/health', periodSeconds: 300, graceSeconds: 120, schedule: null,
        lastPingAt: iso(40 * 60), nextDueAt: String(now() - 15 * 60), alertAfterAt: String(now() - 10 * 60),
        lastAlertAt: iso(9 * 60),
        createdAt: iso(160 * 86400),
        alertChannels: ['chan-mattermost-1', 'chan-webhook-1'],
        tags: ['prod', 'api'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 1, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: '"status":"ok"', failureThreshold: 2,
      },
      {
        // Deliberate edge case: LATE with zero alert channels — should show
        // the amber "alerts disabled" warning on the detail page.
        checkId: 'check-3', teamId: 'team-sre', name: 'payment-webhook-processor', slug: 'payment-webhook-processor',
        token: 'tok_demo_paymentwebhook03', status: 'late', type: 'heartbeat',
        periodSeconds: 900, graceSeconds: 300, schedule: null,
        lastPingAt: iso(2 * HOUR), nextDueAt: String(now() - 40 * 60), alertAfterAt: String(now() - 35 * 60),
        lastAlertAt: null,
        createdAt: iso(30 * 86400),
        alertChannels: [],
        tags: ['prod', 'payments'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-4', teamId: 'team-sre', name: 'cache-warmer', slug: 'cache-warmer',
        token: 'tok_demo_cachewarmer04', status: 'paused', type: 'heartbeat',
        periodSeconds: 600, graceSeconds: 180, schedule: null,
        lastPingAt: iso(3 * 86400), nextDueAt: null, alertAfterAt: null, lastAlertAt: null,
        createdAt: iso(80 * 86400),
        alertChannels: ['chan-mattermost-1'],
        tags: ['staging'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        // Never pinged — exercises the onboarding empty state / curl snippet.
        checkId: 'check-5', teamId: 'team-sre', name: 'etl-hourly-sync', slug: 'etl-hourly-sync',
        token: 'tok_demo_etlhourlysync05', status: 'pending', type: 'cron', schedule: '0 * * * *',
        periodSeconds: null, graceSeconds: 600,
        lastPingAt: null, nextDueAt: String(now() + HOUR), alertAfterAt: String(now() + HOUR + 600), lastAlertAt: null,
        createdAt: iso(15 * 60),
        alertChannels: ['chan-email-1'],
        tags: ['prod', 'etl'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        // Currently suppressed — exercises the amber suppression notice.
        checkId: 'check-6', teamId: 'team-sre', name: 'backup-verification', slug: 'backup-verification',
        token: 'tok_demo_backupverify06', status: 'up', type: 'cron', schedule: '30 3 * * *',
        periodSeconds: null, graceSeconds: 1800,
        lastPingAt: iso(4 * HOUR), nextDueAt: String(now() + 20 * HOUR), alertAfterAt: String(now() + 21 * HOUR),
        lastAlertAt: iso(2 * 86400),
        createdAt: iso(200 * 86400),
        alertChannels: ['chan-mattermost-1'],
        tags: ['prod', 'db'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: 3, suppressDurationMinutes: 240, consecutiveAlertCount: 3,
        suppressedUntil: isoFuture(90 * 60),
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-7', teamId: 'team-sre', name: 'certificate-renewal-check', slug: 'certificate-renewal-check',
        token: 'tok_demo_certcheck07', status: 'up', type: 'http',
        url: 'https://example.com/', periodSeconds: 21600, graceSeconds: 1800, schedule: null,
        lastPingAt: iso(HOUR), nextDueAt: String(now() + 5 * HOUR), alertAfterAt: String(now() + 5 * HOUR + 1800),
        lastAlertAt: null,
        createdAt: iso(140 * 86400),
        alertChannels: ['chan-shared-1'],
        tags: ['prod', 'security'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-8', teamId: 'team-sre', name: 'log-shipper', slug: 'log-shipper',
        token: 'tok_demo_logshipper08', status: 'up', type: 'heartbeat',
        periodSeconds: 300, graceSeconds: 120, schedule: null,
        lastPingAt: iso(2 * 60), nextDueAt: String(now() + 3 * 60), alertAfterAt: String(now() + 5 * 60), lastAlertAt: null,
        createdAt: iso(50 * 86400),
        alertChannels: ['chan-telegram-1'],
        tags: ['staging'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        // Approaching but not yet late (consecutiveFailureCount < threshold)
        checkId: 'check-9', teamId: 'team-sre', name: 'webhook-relay', slug: 'webhook-relay',
        token: 'tok_demo_webhookrelay09', status: 'up', type: 'http',
        url: 'https://relay.example.com/status', periodSeconds: 120, graceSeconds: 60, schedule: null,
        lastPingAt: iso(90), nextDueAt: String(now() + 30), alertAfterAt: String(now() + 90), lastAlertAt: null,
        createdAt: iso(20 * 86400),
        alertChannels: ['chan-webhook-1', 'chan-mattermost-1'],
        tags: ['prod'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 204, expectedString: null, failureThreshold: 3,
      },
      {
        checkId: 'check-10', teamId: 'team-sre', name: 'staging-smoke-test', slug: 'staging-smoke-test',
        token: 'tok_demo_stagingsmoke10', status: 'paused', type: 'cron', schedule: '*/15 * * * *',
        periodSeconds: null, graceSeconds: 300,
        lastPingAt: iso(5 * 86400), nextDueAt: null, alertAfterAt: null, lastAlertAt: null,
        createdAt: iso(70 * 86400),
        alertChannels: [],
        tags: ['staging', 'qa'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
    ],
    'team-data': [
      {
        checkId: 'check-11', teamId: 'team-data', name: 'spark-job-nightly', slug: 'spark-job-nightly',
        token: 'tok_demo_sparknightly11', status: 'up', type: 'cron', schedule: '0 1 * * *',
        periodSeconds: null, graceSeconds: 3600,
        lastPingAt: iso(9 * HOUR), nextDueAt: String(now() + 15 * HOUR), alertAfterAt: String(now() + 16 * HOUR), lastAlertAt: null,
        createdAt: iso(100 * 86400),
        alertChannels: ['chan-data-webhook'],
        tags: ['prod', 'spark'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-12', teamId: 'team-data', name: 'airflow-dag-sync', slug: 'airflow-dag-sync',
        token: 'tok_demo_airflowdag12', status: 'late', type: 'heartbeat',
        periodSeconds: 1800, graceSeconds: 600, schedule: null,
        lastPingAt: iso(50 * 60), nextDueAt: String(now() - 5 * 60), alertAfterAt: String(now() - 2 * 60), lastAlertAt: iso(60),
        createdAt: iso(60 * 86400),
        alertChannels: ['chan-data-webhook'],
        tags: ['prod', 'airflow'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 1, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
      {
        checkId: 'check-13', teamId: 'team-data', name: 'data-quality-check', slug: 'data-quality-check',
        token: 'tok_demo_dataquality13', status: 'pending', type: 'cron', schedule: '0 6 * * *',
        periodSeconds: null, graceSeconds: 900,
        lastPingAt: null, nextDueAt: String(now() + 8 * HOUR), alertAfterAt: String(now() + 8 * HOUR + 900), lastAlertAt: null,
        createdAt: iso(3 * 3600),
        alertChannels: [],
        tags: ['staging'],
        escalationMinutes: null, escalationAlertChannels: [], escalationTriggeredAt: null,
        suppressAfterCount: null, suppressDurationMinutes: null, consecutiveAlertCount: 0, suppressedUntil: null,
        expectedStatusCode: 200, expectedString: null, failureThreshold: 1,
      },
    ],
  },

  // checkId -> pings, newest first. check-2 gets 35 pings to exercise "Load more".
  pings: buildPings(),

  // checkId -> alert delivery history, newest first
  alertHistory: buildAlertHistory(),

  auditLog: {
    'team-sre': buildAuditLog(),
    'team-data': [
      { eventId: 'audit-d1', actorId: 'user-demo-2', actorEmail: 'priya@example.com', action: 'check.created', targetType: 'check', targetId: 'check-13', targetName: 'data-quality-check', detail: null, createdAt: iso(3 * 3600) },
      { eventId: 'audit-d2', actorId: CURRENT_USER.userId, actorEmail: CURRENT_USER.email, action: 'channel.created', targetType: 'channel', targetId: 'chan-data-webhook', targetName: 'Data Eng Webhook', detail: 'type: webhook', createdAt: iso(90 * 86400) },
    ],
  },

  maintenanceWindows: {
    'team-sre': [
      { windowId: 'maint-1', teamId: 'team-sre', checkId: 'check-1', startAt: isoFuture(2 * 86400), endAt: isoFuture(2 * 86400 + 7200), label: 'Planned DB migration', createdBy: CURRENT_USER.userId, createdAt: iso(86400) },
      { windowId: 'maint-2', teamId: 'team-sre', checkId: null, startAt: iso(20 * 3600), endAt: iso(19 * 3600), label: 'Datacenter network maintenance (all checks)', createdBy: 'user-demo-2', createdAt: iso(2 * 86400) },
    ],
    'team-data': [],
  },

  reports: {
    'team-sre': [
      { reportId: 'report-1', teamId: 'team-sre', checkId: null, reportType: 'summary', format: 'json', from: iso(30 * 86400), to: iso(0), status: 'completed', downloadUrl: '/teams/team-sre/reports/report-1/download', createdAt: iso(2 * 3600), createdBy: CURRENT_USER.userId, expiresAt: isoFuture(5 * 86400), fileName: 'summary-report-report-1.json', contentType: 'application/json' },
      { reportId: 'report-2', teamId: 'team-sre', checkId: 'check-2', reportType: 'uptime', format: 'csv', from: iso(7 * 86400), to: iso(0), status: 'completed', downloadUrl: '/teams/team-sre/reports/report-2/download', createdAt: iso(25 * 3600), createdBy: 'user-demo-2', expiresAt: iso(-3600), fileName: 'uptime-report-report-2.csv', contentType: 'text/csv' },
    ],
    'team-data': [],
  },

  apiTokens: {
    'team-sre': [
      { token_id: 'apitok-1', name: 'CI deploy hook', created_at: iso(60 * 86400), last_used_at: iso(3600), expires_at: null, user_id: CURRENT_USER.userId },
      { token_id: 'apitok-2', name: 'Temporary migration script', created_at: iso(10 * 86400), last_used_at: iso(9 * 86400), expires_at: isoFuture(2 * 86400), user_id: 'user-demo-2' },
    ],
    'team-data': [],
  },
}

function buildPings() {
  const pings = {}

  // check-2 (api-health-poll, LATE): rich history including the failure run
  const p2 = []
  for (let i = 0; i < 35; i++) {
    const agoMinutes = i * 5
    const isFailureWindow = i < 3 // most recent 3 are the ongoing outage
    p2.push({
      checkId: 'check-2',
      timestamp: String(now() - agoMinutes * 60),
      receivedAt: iso(agoMinutes * 60),
      pingType: isFailureWindow ? 'fail' : 'success',
      code: isFailureWindow ? '503' : null,
      data: isFailureWindow ? 'Got 503, expected 200' : null,
      responseTimeMs: isFailureWindow ? 8200 + i * 40 : 90 + Math.round(Math.sin(i) * 30),
    })
  }
  pings['check-2'] = p2

  // check-1 (nightly-db-backup): a handful of clean nightly runs
  pings['check-1'] = Array.from({ length: 8 }, (_, i) => ({
    checkId: 'check-1',
    timestamp: String(now() - (i * 86400 + 6 * 3600)),
    receivedAt: iso(i * 86400 + 6 * 3600),
    pingType: 'success',
    code: null,
    data: `Backup completed: ${(1.1 + i * 0.03).toFixed(2)}GB`,
    responseTimeMs: null,
  }))

  // check-3 (payment-webhook-processor, LATE, no channels)
  pings['check-3'] = Array.from({ length: 6 }, (_, i) => ({
    checkId: 'check-3',
    timestamp: String(now() - (i * 900 + 7200)),
    receivedAt: iso(i * 900 + 7200),
    pingType: 'success',
    code: null,
    data: null,
    responseTimeMs: null,
  }))

  pings['check-9'] = Array.from({ length: 12 }, (_, i) => ({
    checkId: 'check-9',
    timestamp: String(now() - i * 120),
    receivedAt: iso(i * 120),
    pingType: i === 1 || i === 2 ? 'fail' : 'success',
    code: i === 1 || i === 2 ? '502' : null,
    data: i === 1 || i === 2 ? 'Got 502, expected 204' : null,
    responseTimeMs: i === 1 || i === 2 ? 4100 : 45,
  }))

  return pings
}

function buildAlertHistory() {
  const history = {}

  history['check-2'] = [
    { deliveryId: 'del-1', checkId: 'check-2', checkName: 'api-health-poll', channelId: 'chan-mattermost-1', channelType: 'mattermost', channelName: 'Platform Oncall (Mattermost)', alertType: 'late', status: 'delivered', attempts: 1, maxAttempts: 5, lastError: null, createdAt: iso(9 * 60), deliveredAt: iso(9 * 60 - 2) },
    { deliveryId: 'del-2', checkId: 'check-2', checkName: 'api-health-poll', channelId: 'chan-webhook-1', channelType: 'webhook', channelName: 'PagerDuty Bridge', alertType: 'late', status: 'pending', attempts: 2, maxAttempts: 5, lastError: 'Connection timeout after 10s', createdAt: iso(9 * 60), deliveredAt: null },
  ]
  history['check-3'] = [] // no channels configured — nothing was ever attempted
  history['check-6'] = [
    { deliveryId: 'del-3', checkId: 'check-6', checkName: 'backup-verification', channelId: 'chan-mattermost-1', channelType: 'mattermost', channelName: 'Platform Oncall (Mattermost)', alertType: 'late', status: 'failed', attempts: 5, maxAttempts: 5, lastError: 'Mattermost returned HTTP 410 (webhook removed)', createdAt: iso(2 * 86400), deliveredAt: null },
    { deliveryId: 'del-4', checkId: 'check-6', checkName: 'backup-verification', channelId: 'chan-mattermost-1', channelType: 'mattermost', channelName: 'Platform Oncall (Mattermost)', alertType: 'late', status: 'delivered', attempts: 1, maxAttempts: 5, lastError: null, createdAt: iso(3 * 86400), deliveredAt: iso(3 * 86400 - 3) },
    { deliveryId: 'del-5', checkId: 'check-6', checkName: 'backup-verification', channelId: 'chan-mattermost-1', channelType: 'mattermost', channelName: 'Platform Oncall (Mattermost)', alertType: 'recovery', status: 'delivered', attempts: 1, maxAttempts: 5, lastError: null, createdAt: iso(3 * 86400 - 1800), deliveredAt: iso(3 * 86400 - 1802) },
  ]
  history['check-12'] = [
    { deliveryId: 'del-6', checkId: 'check-12', checkName: 'airflow-dag-sync', channelId: 'chan-data-webhook', channelType: 'webhook', channelName: 'Data Eng Webhook', alertType: 'late', status: 'delivered', attempts: 1, maxAttempts: 5, lastError: null, createdAt: iso(60), deliveredAt: iso(58) },
  ]

  return history
}

function buildAuditLog() {
  const actors = [
    { id: CURRENT_USER.userId, email: CURRENT_USER.email },
    { id: 'user-demo-2', email: 'priya@example.com' },
    { id: 'user-demo-3', email: 'marcus@example.com' },
  ]
  const entries = [
    ['check.created', 'check', 'check-9', 'webhook-relay', null, 20 * 86400],
    ['channel.created', 'channel', 'chan-telegram-1', 'Mobile Alerts', 'type: telegram', 60 * 86400],
    ['check.paused', 'check', 'check-10', 'staging-smoke-test', null, 15 * 86400],
    ['member.role_changed', 'member', 'user-demo-3', null, 'new role: member', 10 * 86400],
    ['check.token_rotated', 'check', 'check-4', 'cache-warmer', null, 8 * 86400],
    ['channel.deleted', 'channel', 'chan-legacy-slack', 'Legacy Slack (removed)', 'type: webhook', 6 * 86400],
    ['member.invited', 'member', 'new-hire@example.com', 'new-hire@example.com', 'role: member', 2 * 86400],
    ['check.updated', 'check', 'check-6', 'backup-verification', 'changed: suppressAfterCount, suppressDurationMinutes', 40 * 3600],
    ['check.escalated', 'check', 'check-2', 'api-health-poll', null, 9 * 60],
    ['token.created', 'token', 'apitok-2', 'Temporary migration script', null, 10 * 86400],
  ]
  return entries.map(([action, targetType, targetId, targetName, detail, secondsAgo], i) => ({
    eventId: `audit-${i + 1}`,
    actorId: actors[i % actors.length].id,
    actorEmail: actors[i % actors.length].email,
    action, targetType, targetId, targetName, detail,
    createdAt: iso(secondsAgo),
  }))
}

export function findUser(userId) {
  if (userId === CURRENT_USER.userId) return CURRENT_USER
  return OTHER_USERS.find((u) => u.userId === userId) || null
}
