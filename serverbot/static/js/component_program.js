// static/your_app/js/script.js

function loadProgramComponent() {
  fetch("/programs/") // Adjust the URL to match your Django URL pattern
    .then((response) => response.text())
    .then((html) => {
      // Insert the rendered HTML into the component_programs div
      document.getElementById("component_programs").innerHTML = html;
    })
    .catch((error) => {
      console.error("Error loading program component:", error);
    });
}

$(document).ready(function () {
  // Event handler for the button with id 'update-button'
});

function fetchProgramDetails(programId) {
  const url = "{% url 'program' 'program_id' %}".replace("program_id", programId);

  fetch(url, {
    method: "GET",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "Content-Type": "application/json",
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      // Process the received data and update the DOM accordingly
      changeProcessStatusColor(data);
    })
    .catch((error) => {
      console.error("Error fetching program details:", error);
    });
}

// Function to change the color of the rect element
function changeProcessStatusColor(data) {
  // Create an empty object to hold the final dictionary
  const processesStatus = {};

  // Use a loop to combine the keys and values into the object
  for (let i = 0; i < data.keys.length; i++) {
    processesStatus[data.keys[i]] = data.values[i];
  }

  // Now you can use processesStatus as a regular JavaScript object
  console.log(processesStatus);

  for (const [Id, active] of Object.entries(processesStatus)) {
    const rectID = "program_status_rect_rectId".replace("rectId", Id);
    const rectElement = document.getElementById(rectID); // Get the rect element by ID

    const polylineID = "program_status__polyline_rectId".replace("rectId", Id);
    const polylineElement = document.getElementById(polylineID); // Get the rect element by ID

    const polygonID = "program_status_polygon_rectId".replace("rectId", Id);
    const polygonElement = document.getElementById(polygonID); // Get the rect element by ID

    // Change the stroke color if the rect element exists
    if (rectElement) {
      const color = active ? "green" : "red"; // True is green, false is red
      rectElement.setAttribute("stroke", color); // Update the stroke color
      polylineElement.setAttribute("stroke", color); // Update the stroke color
      polygonElement.setAttribute("fill", color); // Update the stroke color
    } else {
      console.error(`Element with ID ${Id} not found.`);
    }
  }
}

function updatePrograms() {
  // Make an AJAX request
  $.ajax({
    // URL where the request is sent
    url: "http://192.168.0.3:5000/api/receive", // Update with the correct URL for your AJAX endpoint
    // HTTP method used for the request
    type: "GET", // Using 'GET' method to fetch data

    // Function to run if the request is successful
    success: function (response) {
      $("#programs_console").html("");
      // Use the response data to dynamically create HTML
      $("#programs_console").append("<h1>" + response.status + "</h1>");
      $("#programs_console").append("<p>Message: " + response.message + "</p>");
    },

    // Function to run if there's an error with the request
    error: function (xhr, status, error) {
      // Log the error to the browser console
      console.error("An error occurred: " + error);
    },
  });
  //getProgramsStatus();
}

function testPrograms() {
  fetch("http://192.168.0.3:5000/api/test", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ message: document.getElementById("test-button").textContent }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok " + response.statusText);
      }
      return response.json();
    })
    .then((data) => {
      $("#programs_console").html("");
      // Replace the content of the element with id 'component_programs' with the new HTML
      $("#programs_console").text(data.message);
    })
    .catch((error) => {});
}
