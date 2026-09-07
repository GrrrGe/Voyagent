from tavily import TavilyClient
import os 
from dotenv import load_dotenv
load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def tavily_search(query: str):
    """
    Search for a query using the Tavily API.

    Args:
        query (str): The search query.
        
    Returns:
        dict: The search results from the Tavily API.
    """
    try:
        response = client.search(query , max_results=5 , search_depth="advanced")
        results = []
        for i , r in enumerate(response['results'] , 1):
            title = r.get('title', 'No Title')
            url = r.get('url', 'No URL')
            snippet = r.get('content', '').strip()
            if len(snippet) > 500:
                snippet = snippet[:500].rsplit(" " , 1)[0] + "..."
            results.append(f"{i}. {title}\nURL: {url}\nSnippet: {snippet}\n")
        return "\n\n".join(results)
        
    except Exception as e:
        print(f"An error occurred while searching: {e}")
        return "An error occurred while searching. Please try again later."