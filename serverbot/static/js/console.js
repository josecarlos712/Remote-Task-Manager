/* console script configuration
console div id = "console"
button with onclick = executeFunction('function ID for execute_function on views_api.py')
*/

function logToConsole(message) {
  const consoleDiv = document.getElementById("console");
  const timestamp = new Date().toLocaleTimeString();
  consoleDiv.innerHTML += "[${timestamp}] ${message}<br>";
  consoleDiv.scrollTop = consoleDiv.scrollHeight;
}

function executeFunction(buttonId) {
  fetch("/api/execute/${buttonId}/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      logToConsole("${buttonId}: ${data.message}");
    })
    .catch((error) => {
      logToConsole("Error executing ${buttonId}: ${error}");
    });
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
