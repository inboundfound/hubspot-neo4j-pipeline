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

    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all users/owners with their properties"""
        self.logger.info("Starting users extraction")

        # Use the owners API endpoint
        # Note: This uses /crm/v3/owners/ endpoint which requires settings.users.read scope
        all_users = []
        after = None

        try:
            while True:
                # Build API call parameters
                kwargs = {
                    'limit': BATCH_SIZE
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
                        # Note: LinkedIn URL may not be available via the owners API
                        # It might be in user settings or profile data
                        if hasattr(user, 'teams'):
                            user_dict['teams'] = [{'id': str(team.id), 'name': team.name} for team in user.teams] if user.teams else []

                        all_users.append(user_dict)

                    # Check for more pages
                    if hasattr(results, 'paging') and results.paging and hasattr(results.paging, 'next'):
                        after = results.paging.next.after
                    else:
                        break
                else:
                    self.logger.warning("No results found for users")
                    break

        except Exception as e:
            self.logger.error(f"Error extracting users: {str(e)}")
            self.logger.error("Make sure the 'settings.users.read' scope is enabled in your HubSpot app")
            # Return empty list if API call fails (e.g., missing scope)
            return []

        self.logger.info(f"Extracted {len(all_users)} users")
        self.data = all_users
        return all_users
