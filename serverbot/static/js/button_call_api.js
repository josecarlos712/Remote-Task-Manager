/* API call script
container is the element to change (change to appropriated name)
button with onclick = executeFunction('function ID for execute_function on views_api.py')
Assumes getCookie and displayErrors (for JSON errors) are accessible.
*/

/**
 * Injects HTML content into a specified container element.
 *
 * @param {string} htmlContent - The HTML string to inject.
 */
function injectHTML(htmlContent) {
  const container = document.getElementById("container");
  if (container) {
    container.innerHTML = htmlContent;
  } else {
    console.error("Error: Container element with ID 'container' not found.");
    console.trace("Origin of the error"); // Showsthe stack trace for debugging
  }
}

/**
 * Fetches HTML content from a specified API URL using AJAX and injects it into the DOM.
 * Uses sendAjaxPostRequestText for the AJAX call.
 *
 * @param {string} url - The API endpoint URL to fetch HTML from.
 */
function getHTMLfromAPI(url) {
  // Optional: Clear the container or show a loading indicator before fetching
  // injectHTML(''); // Clear current content

  sendAjaxPostRequestText(url)
    .then(([success, responseData]) => {
      if (success) {
        // responseData is the HTML string
        //console.log("Successfully fetched HTML.");
        injectHTML(responseData); // Inject the received HTML
      } else {
        // responseData is the error message string
        console.error("Error fetching HTML:", responseData);
        //logToConsole(`Error fetching content: ${responseData}`); // Log the error message
        // TODO: Handle HTML fetching errors more gracefully in the UI if needed (inject an error message into the container)
        // injectHTML(`<p style="color: red;">Failed to load content: ${responseData}</p>`);
      }
    })
    .catch((error) => {
      // Handle network errors or CSRF token missing (Promise rejected)
      console.error("getHTMLfromAPI request failed:", error);
      logToConsole(`Request failed: ${error}`); // Log the rejection reason
      // TODO: Handle request rejection errors gracefully in the UI
    });
}

/**
 * Executes a function on the server via an API call using AJAX.
 * Uses sendAjaxPostRequest for the AJAX call.
 *
 * @param {string} buttonId - The ID associated with the function to execute on the server.
 */
function executeFunction(functionName) {
  // TODO: Ensure the URL pattern for execute function is correct in your Django urls.py
  const url = `/api/execute/${functionName}/`; // Construct the API URL

  // No specific JSON data needed for this execute function call, just the ID in the URL
  const jsonData = {}; // Send an empty object or null if your API expects it

  sendAjaxPostRequest(url, jsonData)
    .then(([success, responseData]) => {
      if (success) {
        // responseData is the parsed JSON response from the server
        console.log(`Execution successful for ${functionName}:`, responseData);
        // Assuming the server response includes a 'message' field on success
        if (responseData && responseData.message) {
          logToConsole(`${responseData.message}`);
        } else {
          logToConsole(`Function ${buttonId} executed successfully.`);
        }

        // TODO: Handle other potential data in responseData if needed
        // e.g., if the server returns updated status or data after execution
      } else {
        // responseData is the parsed JSON error response from the server
        console.error(`Execution failed for ${functionName}:`, responseData);
        // Assumes displayErrors is defined and accessible for validation errors
        if (typeof displayErrors === "function" && responseData && responseData.data) {
          // If responseData.data contains validation errors, display them
          displayErrors(responseData.data); // This logs to console as per your current displayErrors
          logToConsole(`Execution failed for ${functionName} (validation errors).`);
        } else if (responseData && responseData.message) {
          // Display a general error message from the API response
          logToConsole(`Error executing ${functionName}: ${responseData.message}`);
        } else {
          logToConsole(`Error executing ${functionName}.`);
        }
        // TODO: Handle execution errors more gracefully in the UI if needed
      }
    })
    .catch((error) => {
      // Handle network errors or CSRF token missing (Promise rejected)
      console.error(`executeFunction request failed for ${buttonId}:`, error);
      logToConsole(`Request failed for ${buttonId}: ${error}`); // Log the rejection reason
      // TODO: Handle request rejection errors gracefully in the UI
    });
}

/**
 * Logs a message to a specific console element in the DOM.
 * Clears the console if the message is "\n\n\n".
 *
 * @param {string} message - The message to log.
 */
function logToConsole(message) {
  // TODO: Ensure 'console' element exists in your HTML
  const consoleDiv = document.getElementById("console");
  if (consoleDiv) {
    const timestamp = new Date().toLocaleTimeString();
    if (message === "\n\n\n") {
      // Use strict equality
      consoleDiv.innerHTML = "";
    } else {
      // Use textContent for safety to prevent XSS if message comes from external source
      // Or sanitize message if HTML is intended
      const messageElement = document.createElement("div"); // Use a div or p for each message
      messageElement.innerHTML = `[${timestamp}] ${message}`; // Using innerHTML as in original, but be cautious
      consoleDiv.appendChild(messageElement);
    }

    // Auto-scroll to the bottom
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
  } else {
    console.error("Error: Console element with ID 'console' not found.");
    // Fallback to browser console if console element is missing
    console.log(`[${timestamp}] ${message}`);
  }
}

// Function to get CSRF token (assumed to be accessible)
// displayErrors function (assumed to be accessible for JSON errors)
