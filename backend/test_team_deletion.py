#!/usr/bin/env python3
"""Quick test script for team deletion functionality."""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.dynamodb import DynamoDBClient
from app.models import Team, TeamMember, Role

async def test_delete_team():
    """Test the delete_team method."""
    # Use a test table or ensure you're not running against production
    db = DynamoDBClient("pulsechecks-test")  # Make sure this is a test table
    
    # Create a test team
    test_team_id = "test-team-123"
    test_user_id = "test-user-123"
    
    try:
        # Create team
        team = Team(
            team_id=test_team_id,
            name="Test Team for Deletion",
            created_at="2024-01-01T00:00:00Z"
        )
        await db.create_team(team)
        print(f"✅ Created test team: {test_team_id}")
        
        # Add member
        member = TeamMember(
            team_id=test_team_id,
            user_id=test_user_id,
            role=Role.ADMIN,
            joined_at="2024-01-01T00:00:00Z"
        )
        await db.add_team_member(member)
        print(f"✅ Added test member: {test_user_id}")
        
        # Verify team exists
        retrieved_team = await db.get_team(test_team_id)
        if retrieved_team:
            print(f"✅ Team exists: {retrieved_team.name}")
        else:
            print("❌ Team not found after creation")
            return
        
        # Delete team
        await db.delete_team(test_team_id)
        print(f"✅ Deleted team: {test_team_id}")
        
        # Verify team is gone
        deleted_team = await db.get_team(test_team_id)
        if deleted_team is None:
            print("✅ Team successfully deleted")
        else:
            print("❌ Team still exists after deletion")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Testing team deletion functionality...")
    print("⚠️  Make sure you're using a test DynamoDB table!")
    
    # Uncomment the line below to run the test
    # asyncio.run(test_delete_team())
    print("Test script created. Uncomment the asyncio.run line to execute.")
