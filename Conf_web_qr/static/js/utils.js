// static/js/utils.js

/**
 * Utility functions for enhancing the frontend experience
 */
const Utils = (function() {
    
    /**
     * Format a date string to a more readable format
     * @param {string} dateString - ISO date string
     * @param {boolean} includeTime - Whether to include time
     * @returns {string} Formatted date string
     */
    function formatDate(dateString, includeTime = false) {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return dateString;
        
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        };
        
        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
        }
        
        return date.toLocaleDateString(undefined, options);
    }
    
    /**
     * Format currency values
     * @param {number|string} amount - Amount to format
     * @param {string} currency - Currency code (default: INR)
     * @returns {string} Formatted currency string
     */
    function formatCurrency(amount, currency = 'INR') {
        if (amount === null || amount === undefined) return 'N/A';
        
        const numAmount = parseFloat(amount);
        if (isNaN(numAmount)) return amount.toString();
        
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: currency
        }).format(numAmount);
    }
    
    /**
     * Debounce function to limit the rate at which a function can fire
     * @param {Function} func - Function to debounce
     * @param {number} wait - Milliseconds to wait
     * @returns {Function} Debounced function
     */
    function debounce(func, wait = 300) {
        let timeout;
        
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Validate a form field based on type
     * @param {HTMLElement} field - Form field to validate
     * @returns {boolean} True if valid, false otherwise
     */
    function validateField(field) {
        const value = field.value.trim();
        const fieldType = field.dataset.type || field.type;
        
        switch (fieldType) {
            case 'email':
                return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
                
            case 'phone':
                return /^\d{10}$/.test(value);
                
            case 'number':
                return !isNaN(parseFloat(value)) && isFinite(value);
                
            case 'required':
                return value.length > 0;
                
            default:
                return true;
        }
    }
    
    /**
     * Show a loading spinner
     * @param {boolean} show - Whether to show or hide the spinner
     */
    function toggleLoadingSpinner(show) {
        const spinner = document.getElementById('loadingSpinner');
        if (!spinner) return;
        
        if (show) {
            spinner.style.display = 'flex';
        } else {
            spinner.style.display = 'none';
        }
    }
    
    /**
     * Copy text to clipboard
     * @param {string} text - Text to copy
     * @returns {Promise<boolean>} Success state
     */
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Failed to copy: ', err);
            return false;
        }
    }
    
    /**
     * Handle AJAX form submission
     * @param {HTMLFormElement} form - Form element
     * @param {Function} onSuccess - Success callback
     * @param {Function} onError - Error callback
     */
    function handleFormSubmit(form, onSuccess, onError) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Validate form
            const isValid = Array.from(form.elements)
                .filter(el => el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA')
                .every(field => {
                    const valid = validateField(field);
                    if (!valid) {
                        field.classList.add('is-invalid');
                    } else {
                        field.classList.remove('is-invalid');
                    }
                    return valid;
                });
            
            if (!isValid) {
                if (onError) onError('Please correct the errors in the form');
                return;
            }
            
            toggleLoadingSpinner(true);
            
            try {
                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: form.method || 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok && result.success !== false) {
                    if (onSuccess) onSuccess(result);
                } else {
                    if (onError) onError(result.message || 'An error occurred');
                }
            } catch (error) {
                console.error('Form submission error:', error);
                if (onError) onError('An unexpected error occurred');
            } finally {
                toggleLoadingSpinner(false);
            }
        });
    }
    
    // Public API
    return {
        formatDate,
        formatCurrency,
        debounce,
        validateField,
        toggleLoadingSpinner,
        copyToClipboard,
        handleFormSubmit
    };
})();

export default Utils;