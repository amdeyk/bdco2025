// static/js/modules/ui-helpers.js
/**
 * UI Helper Module - Provides enhanced UI functionality
 */
const UIHelpers = (function() {
    
    /**
     * Initialize all tooltips on the page
     */
    function initTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    /**
     * Show alert messages with automatic dismissal
     * @param {string} message - The message to display
     * @param {string} type - The alert type (success, danger, warning, info)
     * @param {number} duration - Time in ms before auto-dismissal
     */
    function showAlert(message, type = 'info', duration = 3000) {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertContainer.appendChild(alertDiv);
        
        if (duration > 0) {
            setTimeout(() => {
                const alert = bootstrap.Alert.getOrCreateInstance(alertDiv);
                alert.close();
            }, duration);
        }
    }
    
    /**
     * Toggle contextual help sections
     */
    function initHelpSystem() {
        document.querySelectorAll('.help-trigger').forEach(button => {
            button.addEventListener('click', function() {
                const helpContent = this.closest('.help-system').querySelector('.help-content');
                if (helpContent.style.display === 'none') {
                    helpContent.style.display = 'block';
                    this.innerHTML = '<i class="fas fa-times-circle"></i>';
                    this.setAttribute('data-bs-original-title', 'Hide Help');
                } else {
                    helpContent.style.display = 'none';
                    this.innerHTML = '<i class="fas fa-question-circle"></i>';
                    this.setAttribute('data-bs-original-title', 'Show Help');
                }
                // Refresh tooltip
                const tooltip = bootstrap.Tooltip.getInstance(this);
                if (tooltip) {
                    tooltip.update();
                }
            });
        });
    }
    
    // Public API
    return {
        init: function() {
            initTooltips();
            initHelpSystem();
        },
        showAlert: showAlert
    };
})();

// Initialize on document ready
document.addEventListener('DOMContentLoaded', function() {
    UIHelpers.init();
});

export default UIHelpers;