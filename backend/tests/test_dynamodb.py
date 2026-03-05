"""Comprehensive tests for DynamoDBClient."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError

from app.db.dynamodb import DynamoDBClient
from app.models import User, Team, TeamMember, Check, Ping, Role, CheckStatus


@pytest.fixture
def db_client():
    """Create DynamoDBClient instance."""
    return DynamoDBClient(table_name="test-table")


@pytest.fixture
def mock_table():
    """Mock DynamoDB table."""
    table = AsyncMock()
    return table


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    return User(
        user_id="user-123",
        email="test@example.com",
        name="Test User",
        created_at="2023-01-01T00:00:00Z"
    )


@pytest.fixture
def sample_team():
    """Sample team for testing."""
    return Team(
        team_id="team-123",
        name="Test Team",
        created_at="2023-01-01T00:00:00Z",
        created_by="user-123"
    )


@pytest.fixture
def sample_check():
    """Sample check for testing."""
    return Check(
        check_id="check-123",
        team_id="team-123",
        name="Test Check",
        token="token-123",
        period_seconds=3600,
        grace_seconds=300,
        status=CheckStatus.UP,
        created_at="2023-01-01T00:00:00Z"
    )


class TestUserOperations:
    """Test user-related database operations."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_client, mock_table, sample_user):
        """Test user creation."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.create_user(sample_user)
            
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args[1]
            item = call_args['Item']
            
            assert item['PK'] == 'USER#user-123'
            assert item['SK'] == 'PROFILE'
            assert item['userId'] == 'user-123'
            assert item['email'] == 'test@example.com'

    @pytest.mark.asyncio
    async def test_get_user_exists(self, db_client, mock_table, sample_user):
        """Test getting existing user."""
        mock_table.get_item.return_value = {
            'Item': {
                'userId': 'user-123',
                'email': 'test@example.com',
                'name': 'Test User',
                'createdAt': '2023-01-01T00:00:00Z'
            }
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            user = await db_client.get_user('user-123')
            
            assert user is not None
            assert user.user_id == 'user-123'
            assert user.email == 'test@example.com'

    @pytest.mark.asyncio
    async def test_get_user_not_exists(self, db_client, mock_table):
        """Test getting non-existent user."""
        mock_table.get_item.return_value = {}
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            user = await db_client.get_user('nonexistent')
            
            assert user is None

    @pytest.mark.asyncio
    async def test_update_user_login(self, db_client, mock_table):
        """Test updating user login time."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.update_user_login('user-123', 'Updated Name')
            
            mock_table.update_item.assert_called_once()
            call_args = mock_table.update_item.call_args[1]
            
            assert call_args['Key'] == {'PK': 'USER#user-123', 'SK': 'PROFILE'}
            assert ':name' in call_args['ExpressionAttributeValues']


class TestTeamOperations:
    """Test team-related database operations."""

    @pytest.mark.asyncio
    async def test_create_team(self, db_client, mock_table, sample_team):
        """Test team creation."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.create_team(sample_team)
            
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args[1]
            item = call_args['Item']
            
            assert item['PK'] == 'TEAM#team-123'
            assert item['SK'] == 'METADATA'
            assert item['teamId'] == 'team-123'

    @pytest.mark.asyncio
    async def test_get_team_exists(self, db_client, mock_table):
        """Test getting existing team."""
        mock_table.get_item.return_value = {
            'Item': {
                'teamId': 'team-123',
                'name': 'Test Team',
                'createdAt': '2023-01-01T00:00:00Z',
                'createdBy': 'user-123'
            }
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            team = await db_client.get_team('team-123')
            
            assert team is not None
            assert team.team_id == 'team-123'
            assert team.name == 'Test Team'

    @pytest.mark.asyncio
    async def test_add_team_member(self, db_client, mock_table):
        """Test adding team member."""
        member = TeamMember(
            team_id='team-123',
            user_id='user-123',
            role=Role.ADMIN,
            joined_at='2023-01-01T00:00:00Z'
        )
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.add_team_member(member)
            
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args[1]
            item = call_args['Item']
            
            assert item['PK'] == 'TEAM#team-123'
            assert item['SK'] == 'MEMBER#user-123'
            assert item['role'] == 'admin'

    @pytest.mark.asyncio
    async def test_list_team_members(self, db_client, mock_table):
        """Test listing team members."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'teamId': 'team-123',
                    'userId': 'user-123',
                    'role': 'admin',
                    'joinedAt': '2023-01-01T00:00:00Z'
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            members = await db_client.list_team_members('team-123')
            
            assert len(members) == 1
            assert members[0].user_id == 'user-123'
            assert members[0].role == Role.ADMIN

    @pytest.mark.asyncio
    async def test_get_team_member(self, db_client, mock_table):
        """Test getting specific team member."""
        mock_table.get_item.return_value = {
            'Item': {
                'teamId': 'team-123',
                'userId': 'user-123',
                'role': 'admin',
                'joinedAt': '2023-01-01T00:00:00Z'
            }
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            member = await db_client.get_team_member('team-123', 'user-123')
            
            assert member is not None
            assert member.user_id == 'user-123'
            assert member.role == Role.ADMIN

    @pytest.mark.asyncio
    async def test_list_user_teams(self, db_client, mock_table):
        """Test listing user's teams."""
        # Mock the scan for memberships
        mock_table.scan.return_value = {
            'Items': [
                {
                    'teamId': 'team-123',
                    'userId': 'user-123',
                    'role': 'admin'
                }
            ]
        }
        
        # Mock the get_team call
        with patch.object(db_client, 'get_team') as mock_get_team:
            mock_get_team.return_value = Team(
                team_id='team-123',
                name='Test Team',
                created_at='2023-01-01T00:00:00Z',
                created_by='user-123'
            )
            
            with patch.object(db_client, '_get_table') as mock_get_table:
                mock_get_table.return_value.__aenter__.return_value = mock_table
                
                teams = await db_client.list_user_teams('user-123')
                
                assert len(teams) == 1
                assert teams[0]['team'].team_id == 'team-123'
                assert teams[0]['role'] == 'admin'

    @pytest.mark.asyncio
    async def test_update_team_mattermost_webhook(self, db_client, mock_table):
        """Test updating team Mattermost webhook URL."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            # Test setting webhook URL
            await db_client.update_team_mattermost_webhook("team-123", "https://chat.example.com/hooks/abc123")
            
            mock_table.update_item.assert_called_with(
                Key={"PK": "TEAM#team-123", "SK": "METADATA"},
                UpdateExpression="SET mattermostWebhookUrl = :url",
                ExpressionAttributeValues={":url": "https://chat.example.com/hooks/abc123"},
            )
            
            # Test removing webhook URL
            mock_table.reset_mock()
            await db_client.update_team_mattermost_webhook("team-123", None)
            
            mock_table.update_item.assert_called_with(
                Key={"PK": "TEAM#team-123", "SK": "METADATA"},
                UpdateExpression="REMOVE mattermostWebhookUrl",
            )


class TestCheckOperations:
    """Test check-related database operations."""

    @pytest.mark.asyncio
    async def test_create_check(self, db_client, mock_table, sample_check):
        """Test check creation."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.create_check(sample_check)
            
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args[1]
            item = call_args['Item']
            
            assert item['PK'] == 'TEAM#team-123'
            assert item['SK'] == 'CHECK#check-123'
            assert item['token'] == 'token-123'

    @pytest.mark.asyncio
    async def test_get_check_by_token(self, db_client, mock_table):
        """Test getting check by token."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'teamId': 'team-123',
                    'name': 'Test Check',
                    'token': 'token-123',
                    'periodSeconds': 3600,
                    'graceSeconds': 300,
                    'status': 'up',
                    'createdAt': '2023-01-01T00:00:00Z',
                    'alertTopics': []
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            check = await db_client.get_check_by_token('token-123')
            
            assert check is not None
            assert check.check_id == 'check-123'
            assert check.token == 'token-123'

    @pytest.mark.asyncio
    async def test_get_check(self, db_client, mock_table):
        """Test getting check by team and check ID."""
        mock_table.get_item.return_value = {
            'Item': {
                'checkId': 'check-123',
                'teamId': 'team-123',
                'name': 'Test Check',
                'token': 'token-123',
                'periodSeconds': 3600,
                'graceSeconds': 300,
                'status': 'up',
                'createdAt': '2023-01-01T00:00:00Z',
                'alertTopics': []
            }
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            check = await db_client.get_check('team-123', 'check-123')
            
            assert check is not None
            assert check.check_id == 'check-123'
            assert check.team_id == 'team-123'

    @pytest.mark.asyncio
    async def test_list_team_checks(self, db_client, mock_table):
        """Test listing team checks."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'teamId': 'team-123',
                    'name': 'Test Check',
                    'token': 'token-123',
                    'periodSeconds': 3600,
                    'graceSeconds': 300,
                    'status': 'up',
                    'createdAt': '2023-01-01T00:00:00Z',
                    'alertTopics': []
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            checks = await db_client.list_team_checks('team-123')
            
            assert len(checks) == 1
            assert checks[0].check_id == 'check-123'

    @pytest.mark.asyncio
    async def test_update_check(self, db_client, mock_table):
        """Test updating check."""
        mock_table.update_item.return_value = {
            'Attributes': {
                'checkId': 'check-123',
                'teamId': 'team-123',
                'name': 'Updated Check',
                'token': 'token-123',
                'periodSeconds': 7200,
                'graceSeconds': 600,
                'status': 'up',
                'createdAt': '2023-01-01T00:00:00Z',
                'alertTopics': []
            }
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            updates = {'name': 'Updated Check', 'periodSeconds': 7200}
            check = await db_client.update_check('team-123', 'check-123', updates)
            
            assert check.name == 'Updated Check'
            assert check.period_seconds == 7200

    @pytest.mark.asyncio
    async def test_update_check_on_ping(self, db_client, mock_table):
        """Test updating check on ping."""
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            updates = {
                'lastPingAt': '2023-01-01T01:00:00Z',
                'nextDueAt': '2023-01-01T02:00:00Z',
                'alertAfterAt': '2023-01-01T02:05:00Z',
                'status': 'up'
            }
            
            result = await db_client.update_check_on_ping('team-123', 'check-123', updates)
            
            mock_table.update_item.assert_called_once()
            # Since method returns bool, we expect True for successful update
            assert result is True

    @pytest.mark.asyncio
    async def test_query_due_checks(self, db_client, mock_table):
        """Test querying due checks."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'teamId': 'team-123',
                    'name': 'Test Check',
                    'token': 'token-123',
                    'periodSeconds': 3600,
                    'graceSeconds': 300,
                    'status': 'up',
                    'createdAt': '2023-01-01T00:00:00Z',
                    'alertTopics': []
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            checks = await db_client.query_due_checks(1672531200, limit=10)
            
            assert len(checks) == 1
            assert checks[0].check_id == 'check-123'


class TestPingOperations:
    """Test ping-related database operations."""

    @pytest.mark.asyncio
    async def test_create_ping(self, db_client, mock_table):
        """Test ping creation."""
        ping = Ping(
            check_id='check-123',
            timestamp='1672531200000',
            received_at='2023-01-01T00:00:00Z',
            ping_type='success'
        )
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.create_ping(ping)
            
            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args[1]
            item = call_args['Item']
            
            assert item['PK'] == 'CHECK#check-123'
            assert item['SK'] == 'PING#1672531200000'

    @pytest.mark.asyncio
    async def test_list_check_pings(self, db_client, mock_table):
        """Test listing check pings."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'timestamp': '1672531200000',
                    'receivedAt': '2023-01-01T00:00:00Z',
                    'pingType': 'success'
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            pings = await db_client.list_check_pings('check-123', limit=10)
            
            assert len(pings) == 1
            assert pings[0].check_id == 'check-123'

    @pytest.mark.asyncio
    async def test_list_check_pings_with_since_filter(self, db_client, mock_table):
        """Test listing check pings with time filter."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'timestamp': '1735027200000',  # 2024-12-24 10:00:00
                    'receivedAt': '2024-12-24T10:00:00Z',
                    'pingType': 'success',
                    'data': 'Recent ping'
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            since_timestamp = 1735020000000  # 2024-12-24 08:00:00
            pings = await db_client.list_check_pings('check-123', limit=50, since=since_timestamp)
            
            assert len(pings) == 1
            assert pings[0].check_id == 'check-123'
            assert pings[0].data == 'Recent ping'
            
            # Verify the query was called with time range
            mock_table.query.assert_called_once()
            call_args = mock_table.query.call_args
            assert call_args[1]['KeyConditionExpression'] == "PK = :pk AND SK BETWEEN :start AND :end"
            assert call_args[1]['ExpressionAttributeValues'][':start'] == f"PING#{since_timestamp}"

    @pytest.mark.asyncio
    async def test_list_check_pings_without_since_filter(self, db_client, mock_table):
        """Test listing check pings without time filter uses original query."""
        mock_table.query.return_value = {
            'Items': [
                {
                    'checkId': 'check-123',
                    'timestamp': '1672531200000',
                    'receivedAt': '2023-01-01T00:00:00Z',
                    'pingType': 'success'
                }
            ]
        }
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            pings = await db_client.list_check_pings('check-123', limit=10, since=None)
            
            assert len(pings) == 1
            assert pings[0].check_id == 'check-123'
            
            # Verify the query was called with begins_with pattern
            mock_table.query.assert_called_once()
            call_args = mock_table.query.call_args
            assert call_args[1]['KeyConditionExpression'] == "PK = :pk AND begins_with(SK, :sk_prefix)"
            assert call_args[1]['ExpressionAttributeValues'][':sk_prefix'] == "PING#"


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_client_error_handling(self, db_client, mock_table):
        """Test handling of DynamoDB client errors."""
        mock_table.get_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}}, 'GetItem'
        )
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            with pytest.raises(ClientError):
                await db_client.get_user('user-123')

    @pytest.mark.asyncio
    async def test_update_check_to_late_conditional_fail(self, db_client, mock_table):
        """Test conditional update failure for late check."""
        mock_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem'
        )
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            result = await db_client.update_check_to_late(
                'team-123', 'check-123', '2023-01-01T00:00:00Z'
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_update_check_to_late_success(self, db_client, mock_table):
        """Test successful update to late status."""
        mock_table.update_item.return_value = {}  # Successful update
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            result = await db_client.update_check_to_late(
                'team-123', 'check-123', '2023-01-01T00:00:00Z'
            )
            
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_check(self, db_client, mock_table):
        """Test deleting check and its pings."""
        # Mock successful deletion and query
        mock_table.delete_item.return_value = {}
        mock_table.query.return_value = {"Items": []}  # No pings to delete
        
        with patch.object(db_client, '_get_table') as mock_get_table:
            mock_get_table.return_value.__aenter__.return_value = mock_table
            
            await db_client.delete_check('team-123', 'check-123')
            
            # Should delete the check item
            mock_table.delete_item.assert_called_with(
                Key={
                    'PK': 'TEAM#team-123',
                    'SK': 'CHECK#check-123'
                }
            )
            
            # Should query for pings
            mock_table.query.assert_called_once()
