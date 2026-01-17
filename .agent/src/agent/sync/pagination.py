# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from time import sleep
try:
    import supabase
except ImportError:
    supabase = None

def fetch_page(cursor: int, page_size: int, retries: int = 3):
    """
    Fetches a page of artifacts based on a cursor and page size with retry mechanics.

    Args:
    cursor (int): The starting index of the page.
    page_size (int): The number of records to fetch.
    retries (int): Number of retries for fetching the data with exponential backoff.

    Returns:
    list: A list of fetched records.

    Raises:
    Exception: Propagates any exception that is not resolved after the retries.
    """
    for attempt in range(retries):
        try:
            results = supabase.from_('artifacts').select("*").range(cursor, cursor + page_size - 1).execute()
            if results.get('data'):
                return results['data']
            else:
                raise Exception("Failed to fetch data or data is empty")
        except Exception as e:
            if attempt < retries - 1:
                sleep(2 ** attempt)
            else:
                raise e