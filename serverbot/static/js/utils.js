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
 * @param {string} url - The API endpoint URL.
 * @param {object} jsonData - The data to send in the request body as a JSON object.
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

function sendAjaxPostRequest(url, jsonData) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open("POST", url, true); // Method, URL, Asynchronous (true)

    // Set request headers
    xhr.setRequestHeader("Content-Type", "application/json");
    // Retrieve and set the CSRF token header
    xhr.setRequestHeader("X-CSRFToken", getCookie("csrftoken"));

    // Define the function to handle the response
    xhr.onload = function () {
      console.log(`DEBUG: AJAX POST status for ${url}: ${xhr.status}`);

      try {
        console.log(`DEBUG: AJAX POST response for ${url}: ${xhr.responseText}`);
        const responseData = JSON.parse(xhr.responseText);

        // Determine success based on HTTP status AND API response structure
        let apiSuccess = false;
        if (xhr.status >= 200 && xhr.status < 300) {
          // HTTP success status
          if (responseData.status === "success" || responseData.success === true) {
            apiSuccess = true;
          }
        }

        if (apiSuccess) {
          // API reported success
          resolve([true, responseData]); // Resolve with success status and data
        } else {
          // API reported an error or HTTP error occurred
          console.error(`API Error or HTTP Error for ${url}:`, responseData);
          resolve([false, responseData]); // Resolve with failure status and the error response data
        }
      } catch (e) {
        // Error parsing JSON response
        console.error(`Error parsing JSON response for ${url}:`, e);
        reject("Error parsing server response."); // Reject the promise on parsing error
      }
    };

    // Define the function to handle network errors
    xhr.onerror = function () {
      console.error(`Network Error for ${url}.`);
      reject("Network Error."); // Reject the promise on network error
    };

    // Send the request with the JSON data in the request body
    xhr.send(JSON.stringify(jsonData));
  });
}

/**
 * Sends an AJAX POST request to a specified URL expecting HTML (text) response.
 *
 * @param {string} url - The API endpoint URL.
 * @returns {Promise<[boolean, string]>} A Promise that resolves with a tuple:
 * - [true, htmlContent]: If the request is successful (HTTP 2xx). htmlContent is the response text.
 * - [false, errorMessage]: If a network error or HTTP error occurs. errorMessage is a string.
 */
function sendAjaxPostRequestText(url) {
  return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.open("POST", url, true); // Method, URL, Asynchronous (true)

      // Set request headers
      // Note: Content-Type is often not strictly necessary for POST if sending empty body,
      // but setting it to text/html might be semantically clearer if the server expects it.
      // If your server *requires* a specific Content-Type for empty POST, set it here.
      // xhr.setRequestHeader("Content-Type", "text/html"); // Optional, depending on server needs

      // Retrieve and set the CSRF token header
      // Assumes getCookie is defined and accessible
      const csrfToken = getCookie("csrftoken");
      if (csrfToken) {
           xhr.setRequestHeader("X-CSRFToken", csrfToken);
      } else {
           console.warn(`CSRF token not found for ${url}. Request might fail.`);
           // Decide how to handle missing CSRF token - reject or proceed?
           // For most POST requests in Django, it's required.
           reject("CSRF token not found.");
           return; // Stop the function if token is missing
      }

      // Define the function to handle the response
      xhr.onload = function () {
          console.log(`DEBUG: AJAX POST status for ${url}: ${xhr.status}`);

          if (xhr.status >= 200 && xhr.status < 300) {
              // HTTP success status
              resolve([true, xhr.responseText]); // Resolve with success status and the response text
          } else {
              // HTTP error status (4xx, 5xx)
              console.error(`HTTP Error for ${url}: ${xhr.status} ${xhr.statusText}`);
              // For text responses, the error body might not be JSON. Return status text.
              resolve([false, `HTTP Error: ${xhr.status} ${xhr.statusText}`]);
          }
      };

      // Define the function to handle network errors
      xhr.onerror = function () {
          console.error(`Network Error for ${url}.`);
          reject("Network Error."); // Reject the promise on network error
      };

      // Send the request (no body needed for this specific function)
      xhr.send(); // Sending no body for this HTML fetching function
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
