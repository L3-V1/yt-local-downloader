(function initializeFormValidation() {
    const validationConfig = window.appConfig || {};
    const validationFieldBaseClass = validationConfig.validationFieldBaseClass || "border-white/10";
    const validationFieldErrorClass = validationConfig.validationFieldErrorClass || "";

    function getFieldErrorElement(field) {
        const container = field.closest("label") || field.parentElement;
        if (!container) {
            return null;
        }

        let errorElement = container.querySelector("[data-field-error]");
        if (errorElement) {
            return errorElement;
        }

        errorElement = document.createElement("p");
        errorElement.setAttribute("data-field-error", "true");
        errorElement.className = "mt-2 hidden text-sm font-medium text-red-200";
        container.appendChild(errorElement);
        return errorElement;
    }

    function addClassTokens(element, classNames) {
        if (!classNames) {
            return;
        }

        element.classList.add(...classNames.split(" "));
    }

    function removeClassTokens(element, classNames) {
        if (!classNames) {
            return;
        }

        element.classList.remove(...classNames.split(" "));
    }

    function setFieldError(field, message) {
        const errorElement = getFieldErrorElement(field);
        field.classList.remove(validationFieldBaseClass);
        addClassTokens(field, validationFieldErrorClass);
        field.setAttribute("aria-invalid", "true");

        if (!errorElement) {
            return;
        }

        errorElement.textContent = message;
        errorElement.classList.remove("hidden");
    }

    function clearFieldError(field) {
        const errorElement = getFieldErrorElement(field);
        removeClassTokens(field, validationFieldErrorClass);
        field.classList.add(validationFieldBaseClass);
        field.removeAttribute("aria-invalid");

        if (!errorElement) {
            return;
        }

        errorElement.textContent = "";
        errorElement.classList.add("hidden");
    }

    function getValidationMessage(field) {
        const value = field.value.trim();

        if (field.hasAttribute("required") && !value) {
            return field.dataset.errorMessageRequired || "Preencha este campo.";
        }

        if (field.maxLength > 0 && value.length > field.maxLength) {
            return field.dataset.errorMessageTooLong || `Use no máximo ${field.maxLength} caracteres.`;
        }

        return "";
    }

    function validateField(field) {
        const message = getValidationMessage(field);
        if (message) {
            setFieldError(field, message);
            return false;
        }

        clearFieldError(field);
        return true;
    }

    function registerFieldListeners(field) {
        field.addEventListener("input", () => validateField(field));
        field.addEventListener("blur", () => validateField(field));
    }

    function handleFormSubmit(event, fields) {
        let firstInvalidField = null;

        for (const field of fields) {
            const isValid = validateField(field);
            if (!isValid && !firstInvalidField) {
                firstInvalidField = field;
            }
        }

        if (!firstInvalidField) {
            return;
        }

        event.preventDefault();
        firstInvalidField.focus();
    }

    function registerValidatedForm(form) {
        const fields = Array.from(form.querySelectorAll("[data-validate-field]"));
        if (!fields.length) {
            return;
        }

        form.setAttribute("novalidate", "novalidate");
        fields.forEach(registerFieldListeners);
        form.addEventListener("submit", (event) => handleFormSubmit(event, fields));
    }

    document.querySelectorAll("[data-validate-form]").forEach(registerValidatedForm);
})();
