/**
 * Formats a date string into a Spanish locale string (e.g., "1 de enero de 2023").
 *
 * @param {string} dateString - The date string to format (e.g., "YYYY-MM-DD").
 * @returns {string} The formatted date string in Spanish.
 */
function formatDateSpanish(dateString) {
  const date = new Date(dateString);
  const options = { year: "numeric", month: "long", day: "numeric" };
  return date.toLocaleDateString("es-ES", options);
}

/**
 * Formats a time string into a Spanish locale time string (e.g., "14:30:00").
 * Assumes the input is a time part (HH:MM:SS) and uses an arbitrary date for formatting.
 *
 * @param {string} timeString - The time string to format (e.g., "HH:MM:SS").
 * @returns {string} The formatted time string in Spanish.
 */
function formatTimeSpanish(timeString) {
  // If timeString is just the time part (HH:MM:SS), we need to create a full date object for toLocaleTimeString to work correctly.
  // We can use an arbitrary date as a base.
  const tempDate = new Date(`2000-01-01T${timeString}Z`); // Assuming UTC, adjust if needed
  const options = { hour: "numeric", minute: "2-digit", second: "2-digit" };
  return tempDate.toLocaleTimeString("es-ES", options);
}

/**
 * Sends an AJAX POST request to a specified URL with JSON data.
 *
 * @param {string} api_url - The API endpoint URL.
 * @param {object} content - The data to send in the request body as a JSON object.
 * @returns {Promise<[boolean, object | string]>} A Promise that resolves with a tuple:
 * - [true, data]: If the request is successful (HTTP 2xx) and the API status is 'success'.
 * 'data' is the parsed JSON response body.
 * - [false, data]: If the request is successful (HTTP 2xx) but the API status is 'error'.
 * 'data' is the parsed JSON error response body (containing status, message, errors, etc.).
 * - [false, errorData]: If the request results in an HTTP error (non-2xx).
 * 'errorData' is the parsed JSON error response body.
 * - [false, string]: If a network error occurs or JSON parsing fails.
 * The string is an error message.
 */
function sendAjaxPostRequestJson(api_url, content) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    url = "http://192.168.0.3:8000/" + api_url; // Construct the full URL for the API endpoint
    xhr.open("POST", url, true); // Method, URL, Asynchronous (true)

    // Retrieve and set the CSRF token header
    // Assumes getCookie is defined and accessible
    const csrfToken = getCookie("csrftoken"); // TODO: Ensure getCookie function is available globally or imported
    if (csrfToken) {
      xhr.setRequestHeader("X-CSRFToken", csrfToken);
    } else {
      console.warn(`CSRF token not found for ${url}. Request might fail.`);
      // For most POST requests in Django, CSRF token is required.
      // Rejecting is appropriate if the token is essential.
      reject("CSRF token not found.");
      return; // Stop the function if token is missing
    }

    let requestBody = null; // Variable to hold the body to be sent

    // Check if content is provided and should be sent as JSON
    if (content !== null && typeof content === "object") {
      try {
        // Set the Content-Type header for JSON requests
        xhr.setRequestHeader("Content-Type", "application/json");
        // Stringify the dictionary content to JSON string
        requestBody = JSON.stringify(content);
        console.log(`DEBUG: Sending JSON body for ${url}: ${requestBody}`);
      } catch (e) {
        console.error(`Error stringifying JSON content for ${url}:`, e);
        reject(`Error preparing JSON content: ${e.message}`);
        return; // Stop the function if JSON stringification fails
      }
    } else if (content === null) {
      console.log(`DEBUG: Sending POST request to ${url} with no body.`);
      // No body needed, no Content-Type header for JSON is necessary.
      // If your server requires a specific Content-Type for empty POST, set it here.
      // xhr.setRequestHeader("Content-Type", "text/plain"); // Example for empty body
    } else {
      console.warn(`DEBUG: Invalid content type provided for ${url}. Expected object or null, but got ${typeof content}. Sending without body.`);
      // Handle cases where content is provided but not an object/null
      // Forcing no body or attempting to send as text might depend on requirements.
      // Sending without body is safer if expecting JSON.
    }

    // Define the function to handle the response
    xhr.onload = function () {
      console.log(`DEBUG: AJAX POST status for ${url}: ${xhr.status}`);

      if (xhr.status >= 200 && xhr.status < 300) {
        // HTTP success status (2xx)
        let responseData = xhr.responseText;
        try {
          // Attempt to parse the response text as JSON
          responseData = JSON.parse(xhr.responseText);
          console.log(`DEBUG: Successfully parsed JSON response for ${url}:`, responseData);
        } catch (e) {
          console.warn(`Could not parse JSON response for ${url}:`, e);
          // If JSON parsing fails, return the raw text response
          // Depending on your API, receiving non-JSON on 2xx might be an error.
          // Decide if you should resolve with raw text or reject here.
          // Resolving with raw text allows the caller to handle non-JSON success.
        }
        resolve([true, responseData]); // Resolve with success status and the parsed/raw response data
      } else {
        // HTTP error status (4xx, 5xx)
        console.error(`HTTP Error for ${url}: ${xhr.status} ${xhr.statusText}`);
        let errorResponse = xhr.responseText;
        try {
          // Attempt to parse error response as JSON (APIs often return JSON errors)
          errorResponse = JSON.parse(xhr.responseText);
          console.log(`DEBUG: Successfully parsed JSON error response for ${url}:`, errorResponse);
        } catch (e) {
          console.warn(`Could not parse JSON error response for ${url}:`, e);
          // If JSON parsing fails, return the raw text response
        }
        // Resolve with false status and the error response (parsed JSON or raw text)
        resolve([false, errorResponse]);
      }
    };

    // Define the function to handle network errors
    xhr.onerror = function () {
      console.error(`Network Error for ${url}.`);
      // Reject the promise on network error
      // Provide a more structured error if needed
      reject({ status: "error", message: "Network Error", code: 0 }); // Reject with an error object
    };

    // Define the function to handle request timeouts
    xhr.ontimeout = function () {
      console.error(`Request timed out for ${url}.`);
      reject({ status: "error", message: "Request timed out", code: 408 }); // Reject with a timeout error object
    };

    // Send the request with the prepared body (or null for no body)
    xhr.send(requestBody);
  });
}

/**
 * Retrieves the value of a specific cookie by its name.
 * This function is commonly used to get the CSRF token cookie in Django projects.
 *
 * @param {string} name - The name of the cookie to retrieve.
 * @returns {string | null} The value of the cookie if found, otherwise null.
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      let cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Displays validation error messages received from the server in the browser console.
 * This function is used for debugging purposes during development.
 *
 * @param {dict} errors - An object where keys are field names
 * and values are arrays of error messages (or other error structures).
 * Can be null or undefined if no specific errors are provided.
 */
function displayErrors(errors) {
  console.log("Received validation errors from server:");

  if (errors) {
    // Iterate through the errors dictionary
    for (const fieldName in errors) {
      // Check if the property belongs to the object itself (not inherited)
      if (errors.hasOwnProperty(fieldName)) {
        const errorMessages = errors[fieldName]; // This should be a list of messages

        if (Array.isArray(errorMessages)) {
          console.log(`  Field: ${fieldName}:`);
          errorMessages.forEach((message) => {
            console.log(`    - ${message}`);
          });
        } else {
          // Handle cases where the error might not be a list
          console.log(`  Field: ${fieldName} - Error: ${errorMessages}`);
        }
      }
    }
  } else {
    console.log("  No specific error details provided.");
  }
}
