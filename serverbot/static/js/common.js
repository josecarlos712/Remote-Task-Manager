function fetchData(keyword) {
  const csrfToken = getCookie("csrftoken"); // Get the CSRF token from the cookie

  return fetch("http://192.168.0.3:8000/api/data/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken, // Include CSRF token in the headers
    },
    body: JSON.stringify({ keyword: keyword }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok " + response.statusText);
      }
      return response.json(); // Parse and return the JSON response
    })
    .catch((error) => {
      console.error("There was an error!", error);
      return { error: "An error occurred" }; // Return a fallback error message
    });
}
