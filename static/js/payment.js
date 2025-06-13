// static/js/payment.js
function showPaymentSuccess(message) {
    if (window.UIHelpers && UIHelpers.showAlert) {
        UIHelpers.showAlert(message, 'success');
    } else {
        alert(message);
    }
}
