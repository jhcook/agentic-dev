from time import sleep
import supabase  # Assuming supabase client is already correctly configured and imported

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