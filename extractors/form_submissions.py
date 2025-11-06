from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.settings import BATCH_SIZE
import logging
import requests

class FormSubmissionsExtractor(BaseExtractor):
    """Extract form submissions from HubSpot using Forms API v1"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_properties_list(self) -> List[str]:
        """
        Not applicable for form submissions - this extractor uses Forms API,
        not the standard CRM objects API
        """
        return []

    def extract_all(self) -> List[Dict[str, Any]]:
        """
        Extract all form submissions using the correct Forms API workflow:
        1. Get list of all forms from /marketing/v3/forms
        2. For each form, get submissions from /form-integrations/v1/submissions/forms/{form_guid}

        Requires 'forms' or 'forms-uploaded-files' scope
        """
        self.logger.info("Starting form submissions extraction")

        all_submissions = []

        try:
            # Step 1: Get all forms from the portal
            forms = self._get_all_forms()
            self.logger.info(f"Found {len(forms)} forms in the portal")

            if not forms:
                self.logger.warning("No forms found in portal")
                return []

            # Step 2: For each form, get its submissions
            total_extracted = 0
            total_with_email = 0

            for form in forms:
                form_guid = form.get('id')
                form_name = form.get('name', 'Unknown')

                if not form_guid:
                    self.logger.warning(f"Form '{form_name}' has no guid, skipping")
                    continue

                try:
                    form_submissions = self._get_form_submissions(form_guid, form_name)
                    if form_submissions:
                        total_with_email += len(form_submissions)
                        all_submissions.extend(form_submissions)

                except Exception as e:
                    self.logger.warning(f"Error getting submissions for form '{form_name}': {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting form submissions: {str(e)}")
            self.logger.error("This might indicate missing 'forms' API scope")
            # Return empty list rather than failing the entire pipeline
            return []

        self.logger.info(f"Extracted {len(all_submissions)} form submissions with email addresses (for contact linking)")
        self.data = all_submissions
        return all_submissions

    def _get_all_forms(self) -> List[Dict[str, Any]]:
        """
        Get all forms from the portal using Forms API v3
        Endpoint: GET /marketing/v3/forms
        """
        all_forms = []
        after = None

        try:
            while True:
                # Use the marketing.forms API
                kwargs = {
                    'limit': min(BATCH_SIZE, 50),  # Forms API max is 50
                    'archived': False
                }
                if after:
                    kwargs['after'] = after

                results = self._make_api_call(
                    self.client.marketing.forms.forms_api.get_page,
                    **kwargs
                )

                if hasattr(results, 'results'):
                    for form in results.results:
                        form_dict = {
                            'id': form.id,
                            'name': form.name if hasattr(form, 'name') else 'Unknown',
                            'form_type': form.form_type if hasattr(form, 'form_type') else None,
                            'created_at': str(form.created_at) if hasattr(form, 'created_at') else None,
                            'updated_at': str(form.updated_at) if hasattr(form, 'updated_at') else None
                        }
                        all_forms.append(form_dict)

                    # Check for pagination
                    if hasattr(results, 'paging') and results.paging and hasattr(results.paging, 'next'):
                        after = results.paging.next.after
                    else:
                        break
                else:
                    break

        except Exception as e:
            self.logger.error(f"Error fetching forms list: {e}")
            raise

        return all_forms

    def _get_form_submissions(self, form_guid: str, form_name: str) -> List[Dict[str, Any]]:
        """
        Get all submissions for a specific form
        Endpoint: GET /form-integrations/v1/submissions/forms/{form_guid}

        Note: This is a legacy v1 endpoint accessed via raw HTTP
        because the Python SDK may not have direct support for it
        """
        submissions = []
        after = None

        # This endpoint is not well-supported in the Python SDK,
        # so we use direct HTTP requests
        access_token = self.client.access_token
        base_url = f"https://api.hubapi.com/form-integrations/v1/submissions/forms/{form_guid}"

        try:
            while True:
                params = {'limit': 50}  # Max limit for this endpoint is 50
                if after:
                    params['after'] = after

                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                }

                response = requests.get(base_url, params=params, headers=headers, timeout=30)

                if response.status_code == 401:
                    self.logger.error("401 Unauthorized - missing 'forms' or 'forms-uploaded-files' scope")
                    raise Exception("Missing required API scope for form submissions")

                if response.status_code == 403:
                    self.logger.warning(f"403 Forbidden for form '{form_name}' - may not have permissions")
                    break

                response.raise_for_status()
                data = response.json()

                # Extract submissions from response
                if 'results' in data and data['results']:
                    for submission in data['results']:
                        # Extract email from form values for contact matching
                        email = self._extract_email_from_values(submission.get('values', []))

                        # Only include submissions with email addresses (for contact linking)
                        if not email:
                            continue

                        submission_dict = {
                            'form_guid': form_guid,
                            'form_name': form_name,
                            'submission_id': submission.get('submittedAt'),  # Use timestamp as ID
                            'submitted_at': submission.get('submittedAt'),
                            'page_url': submission.get('pageUrl'),
                            'page_title': submission.get('pageTitle'),
                            'ip_address': submission.get('ipAddress'),
                            'email': email,  # Extracted for easy contact matching
                            'values': submission.get('values', []),  # Field values
                            'contact_id': submission.get('conversion', {}).get('contact', {}).get('id') if 'conversion' in submission else None
                        }
                        submissions.append(submission_dict)

                    # Check for pagination
                    if 'paging' in data and data['paging'] and 'next' in data['paging']:
                        after = data['paging']['next'].get('after')
                    else:
                        break
                else:
                    break

        except requests.exceptions.HTTPError as e:
            if e.response.status_code not in [401, 403]:  # Already handled these
                self.logger.error(f"HTTP error fetching submissions for form '{form_name}': {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching submissions for form '{form_name}': {e}")
            raise

        return submissions

    def _extract_email_from_values(self, values: List[Dict[str, Any]]) -> str:
        """
        Extract email address from form field values
        Looks for common email field names: email, e_mail, email_address, etc.
        """
        if not values:
            return None

        # Common email field names
        email_field_names = ['email', 'e_mail', 'email_address', 'emailaddress', 'e-mail', 'your_email']

        for value in values:
            field_name = value.get('name', '').lower()
            if field_name in email_field_names:
                email = value.get('value')
                if email and '@' in str(email):  # Basic email validation
                    return str(email).strip().lower()

        return None
