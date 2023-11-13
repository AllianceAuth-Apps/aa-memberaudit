/* Global JS functions and symbols for Member Audit */

function setCookie(cname, cvalue, exhours) {
    const d = new Date();
    d.setTime(d.getTime() + (exhours * 60 * 60 * 1000));
    let expires = "expires=" + d.toUTCString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
    const name = cname + "=";
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

function title(text) {
    return text.replace(/(^\w|\s\w)/g, m => m.toUpperCase());
}

function bool_to_icon(value) {
    if (value === true) {
        return '<i class="fas fa-check boolean-icon-true"></i>';
    }
    else if (value === false) {
        return '<i class="fas fa-times boolean-icon-false"></i>';
    }
    else {
        return '<i class="far fa-question-circle"></i>';
    }
}
