let currentThreadId = localStorage.getItem("voyagent_thread_id") || null;
let latestAnswerMarkdown = "";
let loadingTimer = null;

const LOADING_STEPS = ["flight", "hotel", "itinerary", "final"];

function setPrompt(text) {
    const input = document.getElementById("userInput");
    input.value = text;
    input.focus();
    updateCharCount();
}

function updateCharCount() {
    const input = document.getElementById("userInput");
    const counter = document.getElementById("charCount");
    if (input && counter) {
        counter.textContent = `${input.value.length} / ${input.maxLength}`;
    }
}

function startNewPlan() {
    currentThreadId = null;
    localStorage.removeItem("voyagent_thread_id");

    document.getElementById("resultSection").classList.add("hidden");
    document.getElementById("userInput").value = "";
    updateCharCount();
    hideError();

    const threadInfo = document.getElementById("threadInfo");
    if (threadInfo) threadInfo.textContent = "Thread: -";

    document.getElementById("userInput").focus();
}

function setLoading(isLoading) {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");
    const loadingSection = document.getElementById("loadingSection");

    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
        loadingSection.classList.remove("hidden");
        runLoadingAnimation();
    } else {
        btnText.classList.remove("hidden");
        btnLoader.classList.add("hidden");
        loadingSection.classList.add("hidden");
        stopLoadingAnimation();
    }
}

function runLoadingAnimation() {
    let index = 0;

    LOADING_STEPS.forEach((step) => {
        const el = document.querySelector(`.loading-step[data-step="${step}"]`);
        if (el) el.classList.remove("active", "done");
    });

    const advance = () => {
        LOADING_STEPS.forEach((step, i) => {
            const el = document.querySelector(`.loading-step[data-step="${step}"]`);
            if (!el) return;
            if (i < index) {
                el.classList.add("done");
                el.classList.remove("active");
            } else if (i === index) {
                el.classList.add("active");
                el.classList.remove("done");
            } else {
                el.classList.remove("active", "done");
            }
        });
        index = (index + 1) % (LOADING_STEPS.length + 1);
    };

    advance();
    loadingTimer = setInterval(advance, 1800);
}

function stopLoadingAnimation() {
    if (loadingTimer) {
        clearInterval(loadingTimer);
        loadingTimer = null;
    }
    LOADING_STEPS.forEach((step) => {
        const el = document.querySelector(`.loading-step[data-step="${step}"]`);
        if (el) el.classList.remove("active", "done");
    });
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideError() {
    const errorBox = document.getElementById("errorBox");
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

function renderMarkdownInto(elementId, content, emptyMessage) {
    const box = document.getElementById(elementId);
    const text = (content || "").toString().trim();

    if (!text) {
        box.classList.add("empty-state");
        box.innerText = emptyMessage;
        return;
    }

    box.classList.remove("empty-state");

    if (typeof marked !== "undefined") {
        box.innerHTML = marked.parse(text);
    } else {
        box.innerText = text;
    }
}

function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.tab === tabName);
    });

    document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === `panel-${tabName}`);
    });
}

function showResult(data) {
    latestAnswerMarkdown = data.answer;

    const resultSection = document.getElementById("resultSection");
    const threadInfo = document.getElementById("threadInfo");
    const llmCallsInfo = document.getElementById("llmCallsInfo");

    renderMarkdownInto("resultBox", data.answer, "No overview generated.");
    renderMarkdownInto("flightBox", data.flight_results, "No flight results were returned for this request.");
    renderMarkdownInto("hotelBox", data.hotel_results, "No hotel results were returned for this request.");
    renderMarkdownInto("itineraryBox", data.itinerary, "No itinerary was generated for this request.");

    threadInfo.textContent = `Thread: ${data.thread_id}`;
    llmCallsInfo.textContent = `Agent calls: ${data.llm_calls ?? "-"}`;

    switchTab("overview");

    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please enter your travel request first.");
        input.focus();
        return;
    }

    setLoading(true);

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong while planning your trip.");
        }

        currentThreadId = data.thread_id;
        localStorage.setItem("voyagent_thread_id", currentThreadId);

        showResult(data);

    } catch (error) {
        showError(error.message || "Something went wrong. Please try again.");
    } finally {
        setLoading(false);
    }
}

function copyResult() {
    const activePanel = document.querySelector(".tab-panel.active .result-box");
    const text = activePanel ? activePanel.innerText : "";

    if (!text) {
        showError("Nothing to copy yet.");
        return;
    }

    navigator.clipboard.writeText(text)
        .then(() => {
            const copyBtn = document.querySelector(".copy-btn");
            const oldText = copyBtn.textContent;

            copyBtn.textContent = "Copied!";

            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1400);
        })
        .catch(() => {
            showError("Could not copy result.");
        });
}

function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".download-btn");
    const oldText = downloadBtn.textContent;

    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;

    const options = {
        margin: 0.5,
        filename: "voyagent-travel-plan.pdf",
        image: {
            type: "jpeg",
            quality: 0.98
        },
        html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff",
            scrollX: 0,
            scrollY: 0,
            windowWidth: pdfContent.scrollWidth,
            windowHeight: pdfContent.scrollHeight
        },
        jsPDF: {
            unit: "in",
            format: "a4",
            orientation: "portrait"
        },
        pagebreak: {
            mode: ["avoid-all", "css", "legacy"]
        }
    };

    // html2canvas snapshots based on the window's current scroll offset — if
    // the page isn't pinned to the very top, the first slice comes out blank
    // and real content gets pushed onto later pages.
    window.scrollTo(0, 0);

    requestAnimationFrame(() => {
        html2pdf()
            .set(options)
            .from(pdfContent)
            .save()
            .then(() => {
                downloadBtn.textContent = oldText;
                downloadBtn.disabled = false;
            })
            .catch(() => {
                downloadBtn.textContent = oldText;
                downloadBtn.disabled = false;
                showError("Could not download PDF.");
            });
    });
}

async function checkApiStatus() {
    const statusEl = document.getElementById("apiStatus");
    const dot = statusEl.querySelector(".status-dot");
    const label = statusEl.querySelector(".status-label");

    try {
        const response = await fetch("/health");
        const data = await response.json();

        if (response.ok && data.status === "ok") {
            dot.classList.remove("pending", "offline");
            label.textContent = "Online";
            statusEl.title = "API is online";
        } else {
            throw new Error("Unhealthy");
        }
    } catch (error) {
        dot.classList.remove("pending");
        dot.classList.add("offline");
        label.textContent = "Offline";
        statusEl.title = "Could not reach the API";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    checkApiStatus();
    updateCharCount();

    const input = document.getElementById("userInput");
    if (input) {
        input.addEventListener("input", updateCharCount);
    }

    if (currentThreadId) {
        const threadInfo = document.getElementById("threadInfo");
        if (threadInfo) threadInfo.textContent = `Thread: ${currentThreadId}`;
    }
});

document.addEventListener("keydown", function (event) {
    if (event.ctrlKey && event.key === "Enter") {
        sendMessage();
    }
});
