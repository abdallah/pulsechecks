# Pulsechecks TODO

## High Priority Issues

### ✅ 1. **COMPLETED**: Fix New Check Status Logic
**Status**: DONE - New checks now properly start in "pending" state:
- ✅ New checks created with PENDING status instead of UP
- ✅ Late detector handles pending checks appropriately  
- ✅ Frontend displays pending status correctly
- ✅ Checks transition to UP/LATE only after first ping received

**Original Problem**: A new check was always shown as "up" until it was pinged for the first time, then the system started checking it. This was incorrect behavior.

**Expected**: New checks should start in a "pending" or "waiting" state until first ping, then transition to proper up/late status based on timing.

**Impact**: Users now see accurate status for new checks that haven't been pinged yet.

### ✅ 2. **COMPLETED**: Revamp Alert Settings UI
**Status**: DONE - Alert settings UI completely revamped:
- ✅ Combined "Alert Settings" and "Advanced Alert Settings" sections  
- ✅ Removed Advanced Alerting section entirely (escalation/suppression UI)
- ✅ Alert channel selection working correctly with AlertChannel system
- ✅ Removed old "topics" system UI - using newer channel notifications exclusively
- ✅ Single, clean alert configuration section using only AlertChannel system

**Original Problem**: Alert settings in check page need complete overhaul:
- Combine "Alert Settings" and "Advanced Alert Settings" sections
- Alert channel selection is not working correctly 
- Remove old "topics" system and use newer channel notifications exclusively
- UI is confusing with duplicate/overlapping functionality

**Expected**: Single, clean alert configuration section using only the new AlertChannel system.

**Impact**: Users can now properly configure notifications without confusion from duplicate functionality.

### ✅ 3. **COMPLETED**: Fix Mattermost Message View Button
**Status**: DONE - Mattermost alert messages now have working clickable links:
- ✅ Replaced non-functional action buttons with clickable title links
- ✅ Added markdown "View Check Details" links in message text
- ✅ Configured frontend_url from settings instead of hardcoded value
- ✅ Updated tests to verify clickable functionality

**Original Problem**: The "View" button in Mattermost alert messages was not clickable/working.

**Expected**: View button should link to the check detail page in the frontend.

**Impact**: Users can now click directly from Mattermost alerts to navigate to check details in the web interface.

### ✅ 4. **COMPLETED**: Remove Non-Working Last 24 Hours Ping List
**Status**: DONE - Removed the broken "last 24 hours" ping list feature:
- ✅ Removed 24-hour ping API call from frontend
- ✅ Removed recentPings state variable
- ✅ Removed entire "Last 24 Hours" UI section
- ✅ Updated tests to remove 24-hour ping references
- ✅ Kept "Recent Pings (Latest 20)" section intact

**Original Problem**: The "last 24 hours" ping list feature was not working properly.

**Expected**: Remove this feature entirely to clean up the UI and avoid confusion.

**Impact**: Users no longer see broken/empty ping history that didn't provide value. UI is now cleaner with just the working "Recent Pings" section.

## Implementation Notes

### Check Status Fix
- ✅ COMPLETED: Modified check creation to set initial status as "pending"
- ✅ COMPLETED: Updated late detector to handle pending checks differently
- ✅ COMPLETED: Updated frontend to display pending status appropriately
- ✅ COMPLETED: Only transition to up/late after first successful ping

### Alert Settings Revamp
- Remove legacy alert_topics fields and UI
- Consolidate into single alert configuration section
- Fix alert channel selection persistence
- Ensure alert channels are properly saved and displayed
- Remove SNS topic selection UI (legacy)
- Focus on AlertChannel system (Mattermost, SNS via channels, future Telegram)

### Mattermost View Button Fix
- ✅ COMPLETED: Replaced action buttons with clickable title links and markdown links
- ✅ COMPLETED: Configured frontend URL from settings
- ✅ COMPLETED: Updated tests to verify clickable functionality
- ✅ COMPLETED: Fixed user navigation from Mattermost alerts to check details

### Remove 24h Ping List
- Remove "last 24 hours" ping list from check detail page
- Clean up related API endpoints if no longer needed
- Simplify UI to focus on recent pings only

## Priority
All items are high priority as they affect core functionality and user experience.

## Frontend Improvements
- [x] **COMPLETED**: Add pause/resume button on checks in team checks list for quick status control
- [x] **COMPLETED**: Add bulk operations for checks (pause/resume multiple checks)
- [x] **COMPLETED**: Add check status indicators (up/late/paused) with color coding
- [x] **COMPLETED**: Add last ping time display in checks list
- [x] **COMPLETED**: Add quick edit modal for check settings from list view
- [x] **COMPLETED**: Update period/grace inputs to use minutes instead of seconds in frontend UI

## Team Management
- [x] **COMPLETED**: Add team deletion functionality
  - ✅ API endpoint: `DELETE /teams/{team_id}` 
  - ✅ Database method: `delete_team()` with cascade delete functionality
  - ✅ Cascade delete: team metadata, members, checks, pings, alert channels, invitations, webhooks
  - ✅ Authorization: Only team admins can delete teams
  - ✅ Confirmation mechanism: Requires exact team name confirmation to prevent accidental deletion
  - ✅ Frontend "Danger Zone" tab with secure confirmation modal
  - ✅ Comprehensive test coverage for all functionality
  - ✅ Batch deletion using DynamoDB batch_writer for efficient bulk operations (up to 25 items per batch)
  - ✅ Proper error handling and validation
