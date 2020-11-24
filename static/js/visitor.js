$(function () {
    $('#contact').on('submit', function (e) {
        e.preventDefault();  //prevent form from submitting
        let data = {};
        data.otp = $('#otp').val();
        let faceId = getUrlParameter("faceId");
        if (faceId !== undefined) {
            console.log(faceId)
            data.faceId = faceId;
        }
        let json_data = JSON.stringify(data);
        console.log(json_data);
        user_request(json_data);
    });
});

// ajax request - POST - User authorization through SmartDoor
function user_request(payload) {
    $.ajax({
        method: 'POST',
        // Add URL from API endpoint
        url: 'https://0diraezh13.execute-api.us-east-1.amazonaws.com/v1/visitor',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function (res) {
            var name = null;
            if (res) {
                message = res["body"]["message"]
                console.log(message)
                // Override username value from API response - username
                name = res["body"]["name"];
                console.log(name);
                if (name !== undefined) {
                    document.getElementById("greeting").innerHTML = 'Alohomora!';
                    message = message + '<br> Welcome, ' + name + '!';
                    $("body").css("background-color","#9BDDFF");
                }
            }
            console.log(res);
            $("#contact").hide();
            $("#door").show();
            $(".container").css("margin","20% auto")
            document.getElementById("message").innerHTML = message;
        },
        error: function (err) {
            let message_obj = JSON.parse(err.responseText);
            let message = message_obj.message.content;
            $('#answer').html('Error:' + message).css("color", "red");
            console.log(err);
        }
    });
}

var getUrlParameter = function getUrlParameter(sParam) {
    var sPageURL = window.location.search.substring(1),  // faceId=abc-defg-hlidf
        sParameterName;
    
    sParameterName = sPageURL.split('=');
    if (sParameterName[0] === sParam) {
        return sParameterName[1] === undefined ? true : decodeURIComponent(sParameterName[1]);
    }

};

