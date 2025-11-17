"""
Social media posting utility using Arcade AI.
"""
import os
import requests
from typing import Dict, Optional, List
import time


class ArcadeSocialPoster:
    """Posts content to social media platforms using Arcade AI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the poster with Arcade API key.
        
        Args:
            api_key: Arcade API key. If not provided, reads from ARCADE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('ARCADE_API_KEY')
        if not self.api_key:
            raise ValueError("ARCADE_API_KEY must be provided or set in environment")
        
        self.base_url = "https://api.arcade-ai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # User credentials for authentication
        self.user_email = os.getenv('ARCADE_USER_EMAIL')
        self.user_password = os.getenv('ARCADE_USER_PASSWORD')
    
    def authorize_user(self) -> Dict:
        """
        Authorize user with Arcade.
        
        Returns:
            Authorization response dictionary
        """
        payload = {
            "email": self.user_email,
            "password": self.user_password
        }
        
        response = requests.post(
            f"{self.base_url}/auth/authorize",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Authorization failed: {response.status_code} - {response.text}")
    
    def post_to_twitter(self, content: str, url: Optional[str] = None) -> Dict:
        """
        Post content to Twitter/X using Arcade.
        
        Args:
            content: The text content to post
            url: Optional URL to include in the post
            
        Returns:
            Response dictionary from Arcade API
        """
        # Add URL to content if provided
        full_content = content
        if url:
            full_content = f"{content}\n\n{url}"
        
        payload = {
            "tool": "X.PostTweet",
            "inputs": {
                "text": full_content
            }
        }
        
        response = requests.post(
            f"{self.base_url}/tools/execute",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "platform": "twitter",
                "response": response.json(),
                "content": full_content
            }
        else:
            return {
                "success": False,
                "platform": "twitter",
                "error": f"{response.status_code} - {response.text}",
                "content": full_content
            }
    
    def post_to_linkedin(self, content: str, url: Optional[str] = None, page_id: Optional[str] = None) -> Dict:
        """
        Post content to LinkedIn using Arcade.
        
        Args:
            content: The text content to post
            url: Optional URL to include in the post
            page_id: LinkedIn page ID (if posting to company page)
            
        Returns:
            Response dictionary from Arcade API
        """
        # Add URL to content if provided
        full_content = content
        if url:
            full_content = f"{content}\n\nLearn more: {url}"
        
        payload = {
            "tool": "LinkedIn.CreatePost",
            "inputs": {
                "text": full_content
            }
        }
        
        # Add page_id if posting to company page
        if page_id:
            payload["inputs"]["page_id"] = page_id
        
        response = requests.post(
            f"{self.base_url}/tools/execute",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code in [200, 201]:
            return {
                "success": True,
                "platform": "linkedin",
                "response": response.json(),
                "content": full_content
            }
        else:
            return {
                "success": False,
                "platform": "linkedin",
                "error": f"{response.status_code} - {response.text}",
                "content": full_content
            }
    
    def post_to_all_platforms(
        self, 
        twitter_content: str, 
        linkedin_content: str, 
        url: Optional[str] = None,
        linkedin_page_id: Optional[str] = None,
        delay_between_posts: int = 5
    ) -> List[Dict]:
        """
        Post to both Twitter and LinkedIn with a delay between posts.
        
        Args:
            twitter_content: Content for Twitter post
            linkedin_content: Content for LinkedIn post
            url: Optional URL to include in posts
            linkedin_page_id: LinkedIn page ID for company page posting
            delay_between_posts: Seconds to wait between posts (default: 5)
            
        Returns:
            List of response dictionaries from both platforms
        """
        results = []
        
        # Post to Twitter first
        print("Posting to Twitter/X...")
        twitter_result = self.post_to_twitter(twitter_content, url)
        results.append(twitter_result)
        
        # Wait between posts
        if delay_between_posts > 0:
            print(f"Waiting {delay_between_posts} seconds before posting to LinkedIn...")
            time.sleep(delay_between_posts)
        
        # Post to LinkedIn
        print("Posting to LinkedIn...")
        linkedin_result = self.post_to_linkedin(linkedin_content, url, linkedin_page_id)
        results.append(linkedin_result)
        
        return results
