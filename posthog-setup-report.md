<wizard-report>
# PostHog post-wizard report

The wizard has completed a deep integration of PostHog analytics into the Pulsechecks FastAPI backend. A new `posthog_client.py` module was created to initialize the `Posthog` instance (with exception autocapture enabled) using environment variables, and `atexit` shutdown was registered for clean Lambda container teardown. PostHog settings (`posthog_api_key`, `posthog_host`) were added to the Pydantic `Settings` class and stored in `backend/.env`. The `posthog` package was added to `requirements.txt`. Event tracking was added to five router files covering all critical user flows: registration/identity, team lifecycle, check lifecycle, ping reception, and alert channel management. Users are identified on first registration via `posthog_client.set()` and `identify_context()`.

| Event | Description | File |
|---|---|---|
| `user_registered` | New user profile created on first authenticated access | `backend/app/routers/users.py` |
| `team_created` | A new team was created by a user | `backend/app/routers/teams.py` |
| `team_deleted` | A team and all its data was permanently deleted | `backend/app/routers/teams.py` |
| `team_member_added` | An existing user was added directly to a team | `backend/app/routers/teams.py` |
| `team_member_invited` | A pending invitation was created for a user not yet registered | `backend/app/routers/teams.py` |
| `check_created` | A new monitoring check was created for a team | `backend/app/routers/checks.py` |
| `check_deleted` | A monitoring check was permanently deleted | `backend/app/routers/checks.py` |
| `check_paused` | A monitoring check was paused (alerts suppressed) | `backend/app/routers/checks.py` |
| `check_resumed` | A paused monitoring check was resumed | `backend/app/routers/checks.py` |
| `ping_received` | A successful heartbeat ping was received for a check | `backend/app/routers/ping.py` |
| `check_recovered` | A late check received a success ping and returned to UP status | `backend/app/routers/ping.py` |
| `alert_channel_created` | A new alert notification channel was configured for a team | `backend/app/routers/channels.py` |
| `alert_channel_deleted` | An alert notification channel was removed from a team | `backend/app/routers/channels.py` |

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

- **Dashboard — Analytics basics**: https://us.posthog.com/project/372338/dashboard/1439022
- **User Registrations** (trend): https://us.posthog.com/project/372338/insights/LCuqi6hO
- **Onboarding Funnel** (registered → team created → check created): https://us.posthog.com/project/372338/insights/d3i2SV92
- **Check Created vs Deleted** (net growth): https://us.posthog.com/project/372338/insights/p3tlNQJA
- **Ping Volume & Recoveries** (core product health): https://us.posthog.com/project/372338/insights/bhlrvqjm
- **Team Churn (Deletions)** (churn signal): https://us.posthog.com/project/372338/insights/Su8Iston

### Agent skill

We've left an agent skill folder in your project. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.

</wizard-report>
