import asyncio
from browser_use import Browser

async def find_ipad_mini_deals():
    """
    Navigates to Google, searches for "latest deals for apple ipad mini",
    and prints the content of the search results page.
    """
    # Initialize the Browser
    # Browser constructor can take various arguments to customize its behavior,
    # such as 'headless=False' to watch the browser actions.
    browser = Browser()

    try:
        print("Navigating to Google.com...")
        # Navigate to Google's homepage
        await browser.navigate("https://www.google.com")

        print("Typing search query...")
        # Find the search input element (usually named 'q') and type the search query.
        # The `type` method also simulates pressing Enter by default after typing.
        await browser.type("textarea[name='q']", "latest deals for apple ipad mini")

        print("Search submitted. Waiting for results...")
        # Wait for navigation to complete after search submission if necessary.
        # Often, the 'type' command with Enter simulation handles this.
        # Adding a small delay or explicit wait if needed, but browser-use tries to manage this.

        print("\n--- Search Results Page Content (Partial) ---")
        # Get the text content of the current page (search results)
        # The 'text_content' of the body will give us the visible text.
        # We can also use 'page_content' to get the full HTML.
        page_text = await browser.text_content("body")

        # Print a portion of the results
        print(page_text[:2000]) # Print the first 2000 characters as a sample
        print("--------------------------------------------")
        print("\nExtraction of specific deals requires more sophisticated parsing")
        print("of the page structure, which can vary. This script provides the raw search results text.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the browser session
        print("Closing browser...")
        await browser.close()

if __name__ == "__main__":
    # browser-use is async, so we run the main function in an event loop.
    asyncio.run(find_ipad_mini_deals())
