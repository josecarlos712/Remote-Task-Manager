/* API call script
container is the element to change (change to appropriated name)
button with onclick = executeFunction('function ID for execute_function on views_api.py')
*/

function injectHTML(body) {
  const container = document.getElementById("container");
  container.innerHTML = body;
}

function getHTMLfromAPI(url) {
  injectHTML();
  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "text/html",
      "X-CSRFToken": getCookie("csrftoken"),
    },
  })
    .then((response) => response.text())
    .then((html) => {
      // Inject the returned HTML into a specific element in the DOM
      injectHTML(html)
    })
    .catch((error) => {
      console.error("Error fetching HTML:", error);
    });
}

function executeFunction(buttonId) {
  fetch(`/api/execute/${buttonId}/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      logToConsole(`${data.message}`);
    })
    .catch((error) => {
      logToConsole(`Error executing ${buttonId}: ${error}`);
    });
}

function logToConsole(message) {
  const consoleDiv = document.getElementById("console");
  const timestamp = new Date().toLocaleTimeString();
  if(message=="\n\n\n") {
    consoleDiv.innerHTML = "";
  } else {
    consoleDiv.innerHTML += `[${timestamp}] ${message}<br>`;
  }
  
  consoleDiv.scrollTop = consoleDiv.scrollHeight;
}

// Function to get CSRF token
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
