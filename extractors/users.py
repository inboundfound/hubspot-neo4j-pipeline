from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.settings import BATCH_SIZE
import logging

class UsersExtractor(BaseExtractor):
    """Extract all users/owners from HubSpot"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_properties_list(self) -> List[str]:
        """Users endpoint doesn't use properties parameter - returns all fields"""
        return []

    def _extract_users_by_status(self, archived: bool = False) -> List[Dict[str, Any]]:
        """
        Extract users with a specific archived status.
        
        Args:
            archived: If True, fetch archived users; if False, fetch active users
        """
        status_label = "archived" if archived else "active"
        self.logger.info(f"Fetching {status_label} users...")
        
        users = []
        after = None

        while True:
            # Build API call parameters
            kwargs = {
                'limit': BATCH_SIZE,
                'archived': archived
            }
            if after:
                kwargs['after'] = after

            # Call the owners API
            results = self._make_api_call(
                self.client.crm.owners.owners_api.get_page,
                **kwargs
            )

            if hasattr(results, 'results'):
                batch = results.results
                for user in batch:
                    user_dict = {
                        'id': user.id,
                        'email': user.email if hasattr(user, 'email') else '',
                        'first_name': user.first_name if hasattr(user, 'first_name') else '',
                        'last_name': user.last_name if hasattr(user, 'last_name') else '',
                        'archived': user.archived if hasattr(user, 'archived') else False,
                        'created_at': str(user.created_at) if hasattr(user, 'created_at') else None,
                        'updated_at': str(user.updated_at) if hasattr(user, 'updated_at') else None,
                        'user_id': user.user_id if hasattr(user, 'user_id') else None,
                    }

                    # Add optional fields if available
                    if hasattr(user, 'teams'):
                        user_dict['teams'] = [{'id': str(team.id), 'name': team.name} for team in user.teams] if user.teams else []

                    users.append(user_dict)

                # Check for more pages
                if hasattr(results, 'paging') and results.paging and hasattr(results.paging, 'next'):
                    after = results.paging.next.after
                else:
                    break
            else:
                self.logger.warning(f"No results found for {status_label} users")
                break
        
        self.logger.info(f"Fetched {len(users)} {status_label} users")
        return users

    def extract_all(self) -> List[Dict[str, Any]]:
        """
        Extract all users/owners from HubSpot, including both active and archived users.
        Archived users are marked with archived=True to maintain complete ownership history.
        """
        self.logger.info("Starting users extraction (active + archived)")

        try:
            # Fetch active users
            active_users = self._extract_users_by_status(archived=False)
            
            # Fetch archived users
            archived_users = self._extract_users_by_status(archived=True)
            
            # Combine both lists
            all_users = active_users + archived_users
            
            self.logger.info(
                f"Extracted {len(all_users)} total users "
                f"({len(active_users)} active, {len(archived_users)} archived)"
            )

        except Exception as e:
            self.logger.error(f"Error extracting users: {str(e)}")
            self.logger.error("Make sure the 'settings.users.read' scope is enabled in your HubSpot app")
            # Return empty list if API call fails (e.g., missing scope)
            return []

        self.data = all_users
        return all_users
