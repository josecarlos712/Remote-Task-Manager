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
 * Sends an AJAX GET request to a specified URL.
 *
 * @param {string} api_url - The API endpoint URL (e.g., 'api/activity/list/').
 * Query parameters should be included in this string if needed.
 * @returns {Promise<[boolean, object | string]>} A Promise that resolves with a tuple:
 * - [true, data]: If the request is successful (HTTP 2xx) and the response is parseable JSON.
 * 'data' is the parsed JSON response body.
 * - [true, rawText]: If the request is successful (HTTP 2xx) but the response is not parseable JSON.
 * 'rawText' is the raw response text.
 * - [false, errorData]: If the request results in an HTTP error (non-2xx) and the response is parseable JSON.
 * 'errorData' is the parsed JSON error response body.
 * - [false, rawText]: If the request results in an HTTP error (non-2xx) and the response is not parseable JSON.
 * 'rawText' is the raw response text.
 * - [false, string]: If a network error occurs or the request cannot be sent.
 * The string is an error message.
 */
function sendAjaxGetRequest(api_url) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    // Construct the full URL for the API endpoint
    // TODO: Replace with your actual base URL or make it configurable
    const baseUrl = "http://192.168.0.3:8000/";
    const url = baseUrl + api_url;

    xhr.open("GET", url, true); // Method, URL, Asynchronous (true)

    // --- CSRF Token for GET Requests ---
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) {
      xhr.setRequestHeader("X-CSRFToken", csrfToken); // Usually NOT needed for GET
    }

    // Define the function to handle the response
    xhr.onload = function () {
      console.log(`DEBUG: AJAX GET status for ${url}: ${xhr.status}`);

      let responseData = xhr.responseText;
      let isJson = false;

      try {
        // Attempt to parse the response text as JSON
        responseData = JSON.parse(xhr.responseText);
        isJson = true;
        console.log(`DEBUG: Successfully parsed JSON response for ${url}:`, responseData);
      } catch (e) {
        console.warn(`Could not parse JSON response for ${url}:`, e);
        // If JSON parsing fails, responseData remains the raw text
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        // HTTP success status (2xx)
        resolve([true, responseData]); // Resolve with success status and the parsed/raw response data
      } else {
        // HTTP error status (non-2xx)
        console.error(`HTTP Error for ${url}: ${xhr.status} ${xhr.statusText}`);
        // Resolve with false status and the error response (parsed JSON or raw text)
        resolve([false, responseData]);
      }
    };

    // Define the function to handle network errors
    xhr.onerror = function () {
      console.error(`Network Error for ${url}.`);
      reject([false, "Network Error"]); // Reject the promise on network errors
    };

    // Define the function to handle request timeouts
    xhr.ontimeout = function () {
      console.error(`Request Timeout for ${url}.`);
      reject([false, "Request Timeout"]); // Reject the promise on timeout
    };

    // Send the request
    // For GET requests, the send() method takes no arguments.
    xhr.send();
    console.log(`DEBUG: Sending GET request to ${url}.`);
  });
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
      reject({ status: "error", message: "CSRF token not found for POST request. Please ensure you are logged in or the token is set.", code: 403 });
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
        reject({ status: "error", message: "Failed to stringify JSON content for POST request. Please check the content structure.", code: 400 });
        return; // Stop the function if JSON stringification fails
      }
    } else if (content === null) {
      console.log(`DEBUG: Sending POST request to ${url} with no body.`);
      // No body needed, no Content-Type header for JSON is necessary.
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

function timeAgo(date) {
  const now = Date.now(); // Current time in milliseconds
  const timeDifference = now - new Date(date);

  const days = Math.floor(timeDifference / (1000 * 60 * 60 * 24));
  const hours = Math.floor((timeDifference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((timeDifference % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((timeDifference % (1000 * 60)) / 1000);

  const timeAgoParts = [];
  //console.log("Time difference:", now, " - ", new Date(date), " = ", timeDifference, "ms");

  if (days > 0) {
    timeAgoParts.push(`${days} ${days === 1 ? "día" : "días"}`);
  }
  if (hours > 0) {
    timeAgoParts.push(`${hours} ${hours === 1 ? "hora" : "horas"}`);
  }
  if (minutes > 0) {
    timeAgoParts.push(`${minutes} ${minutes === 1 ? "minuto" : "minutos"}`);
  }
  if (seconds > 0 && timeAgoParts.length === 0) {
    timeAgoParts.push(`${seconds} ${seconds === 1 ? "segundo" : "segundos"}`);
  }

  if (timeAgoParts.length > 0) {
    if (timeAgoParts.length > 1) {
      return `hace ${timeAgoParts.slice(0, -1).join(", ")} y ${timeAgoParts[timeAgoParts.length - 1]}`;
    } else {
      return `hace ${timeAgoParts[0]}`;
    }
  } else {
    return "justo ahora";
  }
}

/**
 * Displays a message in a message box on the page.
 * This function is used to show success or error messages to the user.
 * @param {string} message - The message to display.
 * @param {string} type - The type of message ('success', 'error', etc.).
 * This function needs a message box element with the ID "message-display" in the HTML.
 */
function displayMessage(container, message, type) {
  // If the container is not provided, use the default message box
  if (!container) {
    const messageBox = document.getElementById("message-display");
  } else if (typeof container === "string") {
    const messageBox = document.getElementById(container);
  }
  const messageBox = document.getElementById("message-display");
  messageBox.style.display = "block";
  messageBox.className = `message-box ${type}`;
  messageBox.textContent = message;
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

function objectToString(obj) {
  return JSON.stringify(obj, null, 2); // The 'null, 2' arguments are for pretty-printing
}


function askForConfirmationWrapper(func, message="¿Estás seguro de que quieres continuar?", ...args) {
  return new Promise((resolve, reject) => {
    // This is a browser-specific function; for Node.js, you'd use a different way to get user input.
    const confirmation = confirm(message);

    if (confirmation) {
      try {
        // Execute the original function with its arguments
        // We use Promise.resolve() to ensure the result is always a Promise,
        // even if func returns a non-Promise value.
        // This makes the chain more consistent.
        Promise.resolve(func(...args))
          .then(result => resolve(result)) // If func resolves, resolve the wrapper's Promise
          .catch(error => reject(error)); // If func rejects, reject the wrapper's Promise
      } catch (error) {
        // Catch synchronous errors thrown by func itself
        reject(error);
      }
    } else {
      // If action is cancelled, reject the Promise
      reject(new Error("Action cancelled by user."));
    }
  });
}