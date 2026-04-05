#!/usr/bin/env python3
"""
Cost Amplification Test
Tests that high-volume ping spam doesn't trigger proportional cost explosion.

Usage:
  export API_URL=https://pulsechecks-api-prod.run.app
  export CHECK_TOKEN=<token>
  export TEAM_ID=<team>
  export USER_TOKEN=<jwt>
  python3 test_cost_amplification.py
"""

import asyncio
import aiohttp
import os
import sys
import time
from datetime import datetime
import json

API_URL = os.getenv("API_URL", "https://pulsechecks-api-prod.run.app")
CHECK_TOKEN = os.getenv("CHECK_TOKEN", "")
TEAM_ID = os.getenv("TEAM_ID", "")
USER_TOKEN = os.getenv("USER_TOKEN", "")

# Test parameters
CONCURRENT_PINGS = 100  # Concurrent requests
DURATION_SECONDS = 30   # How long to spam pings
TARGET_RATE = 100       # Pings per second (roughly)

class CostAmplificationTester:
    def __init__(self):
        self.ping_count = 0
        self.error_count = 0
        self.rate_limit_count = 0
        self.start_time = None
        self.end_time = None
        self.errors = []
    
    async def send_ping(self, session, check_token):
        """Send a single ping."""
        try:
            url = f"{API_URL}/ping/{check_token}/success"
            async with session.post(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 429:
                    self.rate_limit_count += 1
                    return 429
                elif resp.status == 200:
                    self.ping_count += 1
                    return 200
                else:
                    self.error_count += 1
                    return resp.status
        except asyncio.TimeoutError:
            self.error_count += 1
            self.errors.append("timeout")
            return "timeout"
        except Exception as e:
            self.error_count += 1
            self.errors.append(str(e))
            return "exception"
    
    async def spam_pings(self, check_token):
        """Continuously send pings for DURATION_SECONDS."""
        async with aiohttp.ClientSession() as session:
            self.start_time = time.time()
            tasks = []
            ping_num = 0
            
            while time.time() - self.start_time < DURATION_SECONDS:
                # Queue up CONCURRENT_PINGS tasks at a time
                while len(tasks) < CONCURRENT_PINGS:
                    tasks.append(self.send_ping(session, check_token))
                    ping_num += 1
                
                # Wait for some to complete
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED, timeout=0.1
                )
                for task in done:
                    await task
            
            # Wait for remaining tasks
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self.end_time = time.time()
    
    async def create_webhook_channel(self, user_token, team_id):
        """Create a webhook channel to track cost."""
        async with aiohttp.ClientSession() as session:
            url = f"{API_URL}/teams/{team_id}/channels"
            headers = {
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "name": f"cost-test-{int(time.time())}",
                "type": "webhook",
                "configuration": {
                    "url": "https://webhook.site/test-endpoint"
                }
            }
            
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("id")
                else:
                    print(f"Failed to create channel: {resp.status}")
                    return None
    
    def print_results(self):
        """Print test results."""
        elapsed = self.end_time - self.start_time
        ping_rate = self.ping_count / elapsed if elapsed > 0 else 0
        
        print("\n" + "="*60)
        print("Cost Amplification Test Results")
        print("="*60)
        print(f"Duration:           {elapsed:.1f}s")
        print(f"Pings Sent:         {self.ping_count}")
        print(f"Ping Rate:          {ping_rate:.1f}/sec")
        print(f"Rate Limit (429):   {self.rate_limit_count}")
        print(f"Errors:             {self.error_count}")
        print(f"Total Requests:     {self.ping_count + self.rate_limit_count + self.error_count}")
        
        if self.rate_limit_count > 0:
            rate_limit_pct = (self.rate_limit_count / (self.ping_count + self.rate_limit_count)) * 100
            print(f"Rate Limited (%):   {rate_limit_pct:.1f}%")
        
        print("="*60)
        
        # Analysis
        print("\nAnalysis:")
        if self.rate_limit_count == 0:
            print("⚠️  WARNING: No rate limiting detected!")
            print("   Cost amplification is possible.")
            return False
        elif self.rate_limit_count > (self.ping_count * 0.3):
            print("✅ GOOD: Rate limiting is active and effective")
            print(f"   Only {(self.ping_count / (self.ping_count + self.rate_limit_count) * 100):.1f}% of requests succeeded")
            return True
        else:
            print("⚠️  WARNING: Rate limiting is weak")
            print(f"   {(self.ping_count / (self.ping_count + self.rate_limit_count) * 100):.1f}% of requests succeeded")
            return False
    
    async def run(self, check_token, user_token, team_id):
        """Run the full test."""
        print("Cost Amplification Test")
        print("-" * 60)
        print(f"API URL:            {API_URL}")
        print(f"Check Token:        {check_token[:20]}...")
        print(f"Duration:           {DURATION_SECONDS}s")
        print(f"Concurrent Pings:   {CONCURRENT_PINGS}")
        print(f"Target Rate:        ~{TARGET_RATE}/sec")
        print("-" * 60)
        
        # Create webhook channel
        print("\nCreating webhook channel to track alert costs...")
        channel_id = await self.create_webhook_channel(user_token, team_id)
        if channel_id:
            print(f"Channel created: {channel_id}")
            print("(Alerts sent to this channel during test would indicate cost amplification)")
        
        print(f"\nSpamming {TARGET_RATE * DURATION_SECONDS} pings over {DURATION_SECONDS}s...")
        await self.spam_pings(check_token)
        
        success = self.print_results()
        return success

async def main():
    if not all([CHECK_TOKEN, TEAM_ID, USER_TOKEN]):
        print("Error: Set CHECK_TOKEN, TEAM_ID, and USER_TOKEN env vars")
        print("\nUsage:")
        print("  export API_URL=https://pulsechecks-api-prod.run.app")
        print("  export CHECK_TOKEN=<check-token>")
        print("  export TEAM_ID=<team-id>")
        print("  export USER_TOKEN=<jwt-token>")
        print("  python3 test_cost_amplification.py")
        sys.exit(1)
    
    tester = CostAmplificationTester()
    success = await tester.run(CHECK_TOKEN, USER_TOKEN, TEAM_ID)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
