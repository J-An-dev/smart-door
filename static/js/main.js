$(function () {
    loadImage();
    $('#contact').on('submit', function (e) {
        e.preventDefault();  //prevent form from submitting
        let data = {};
        data.v_name = $('#v_name').val();
        data.v_number = $('#v_number').val();
        let image_key = getUrlParameter("image");
        if (image_key !== undefined) {
            console.log(image_key)
            data.image_key = image_key;
        }
        let json_data = JSON.stringify(data);
        console.log(json_data);
        send_request(json_data);
    });
});

// ajax request - POST method for owner
function send_request(payload) {
    $.ajax({
        method: 'POST',
        url: 'https://0diraezh13.execute-api.us-east-1.amazonaws.com/v1/owner',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function (res) {
            if (res) {
                message = res["body"]["message"]
                console.log(message)
            }
            $('#answer').html(message).css("color", "green").css("font-size", "20px");
            $('#contact-submit').prop('disabled', true);

            console.log(res);
            console.log(message);
        },
        error: function (err) {
            let message_obj = JSON.parse(err.responseText);
            let message = message_obj.message.content;
            $('#answer').html('Error:' + message).css("color", "red").css("font-size", "20px");
            console.log(err);
        }
    });
}

var getUrlParameter = function getUrlParameter(sParam) {
    var sPageURL = window.location.search.substring(1),  //image=kvs1_20201112-224107.jpeg
        sParameterName,
    
    sParameterName = sPageURL.split('=');
    if (sParameterName[0] === sParam) {
        return sParameterName[1] === undefined ? true : decodeURIComponent(sParameterName[1]);
    }
};

function loadImage() {
    console.log(getUrlParameter("image"));
    if (getUrlParameter("image") !== undefined && getUrlParameter("image")) {
        document.getElementById("visitor-img").src = 'https://smart-door-2020.s3.amazonaws.com/' + getUrlParameter("image");
    }
    else {
        document.getElementById("visitor-img").src = 'https://smart-door-2020.s3.amazonaws.com/not-found.png';
    }
}
