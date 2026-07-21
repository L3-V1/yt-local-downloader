export function getPopupElements() {
    return {
        apiBaseUrlInput: document.getElementById("apiBaseUrl"),
        videoUrlText: document.getElementById("videoUrlText"),
        videoFormatSelect: document.getElementById("videoFormat"),
        videoQualitySelect: document.getElementById("videoQuality"),
        statusMessage: document.getElementById("statusMessage"),
        downloadButton: document.getElementById("downloadButton"),
    };
}
