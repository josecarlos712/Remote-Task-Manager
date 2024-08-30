// static/your_app/js/script.js

// This function runs once the document (web page) is fully loaded
$(document).ready(function() {

    // Event handler for the button with id 'update-button'
    $('#update-button').click(function() {

        // Make an AJAX request
        $.ajax({
            // URL where the request is sent
           url: '/programs/',  // Update with the correct URL for your AJAX endpoint
            // HTTP method used for the request
           type: 'GET',  // Using 'GET' method to fetch data

            // Function to run if the request is successful
           success: function(response) {
                    $('#component_programs').html("");
                    // Replace the content of the element with id 'component_programs' with the new HTML
                    $('#component_programs').html(response);
           },

            // Function to run if there's an error with the request
           error: function(xhr, status, error) {
                // Log the error to the browser console
                console.error("An error occurred: " + error);
           }
        });
    });
});
