const chatbotUserId = localStorage.getItem("finadvisor_user_id") || "00000000-0000-0000-0000-000000000001";
let chatbotSessionId = null;
let chatbotIsOpen = false;
let chatbotIsLoading = false;
let chatbotInitialized = false;

const chatbotAuthHeaders = {
  "X-User-Id": chatbotUserId,
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function categoryIcon(category) {
  const map = {
    balance: "wallet",
    spending: "shopping-bag",
    cards: "credit-card",
    emi: "calendar",
    transactions: "list",
    health: "heart-pulse",
    budget: "target",
  };
  return map[category] || "message-circle";
}

function scrollToBottom() {
  const msgs = document.getElementById("chatMessages");
  if (!msgs) return;
  msgs.scrollTop = msgs.scrollHeight;
}

function clearSuggestions() {
  document.querySelectorAll(".chatbot-suggestion-row").forEach((node) => node.remove());
}

function buildInsightBlock(titleText, items, toneClass) {
  const block = document.createElement("div");
  block.className = `chatbot-insight-block ${toneClass || ""}`.trim();

  const title = document.createElement("div");
  title.className = "chatbot-insight-title";
  title.textContent = titleText;
  block.appendChild(title);

  const grid = document.createElement("div");
  grid.className = "chatbot-insight-grid";

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = `chatbot-insight-card tone-${item.tone || "neutral"}`;

    const label = document.createElement("div");
    label.className = "chatbot-insight-label";
    label.textContent = item.title || "Insight";

    card.appendChild(label);

    if (item.value) {
      const value = document.createElement("div");
      value.className = "chatbot-insight-value";
      value.textContent = item.value;
      card.appendChild(value);
    }

    if (item.detail) {
      const detail = document.createElement("div");
      detail.className = "chatbot-insight-detail";
      detail.textContent = item.detail;
      card.appendChild(detail);
    }

    grid.appendChild(card);
  });

  block.appendChild(grid);
  return block;
}

function appendBotMessage(text, meta = null) {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;

  const row = document.createElement("div");
  row.className = "chatbot-row bot";

  const avatar = document.createElement("div");
  avatar.className = "chatbot-mini-avatar";
  avatar.innerHTML = '<i data-lucide="bot"></i>';

  const contentWrap = document.createElement("div");
  contentWrap.className = "chatbot-bubble-wrap";

  const bubble = document.createElement("div");
  bubble.className = "chatbot-bubble bot";
  bubble.innerHTML = String(text || "").replace(/\n/g, "<br>");

  const ts = document.createElement("div");
  ts.className = "chatbot-ts";
  ts.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  contentWrap.appendChild(bubble);

  if (meta && Array.isArray(meta.insights) && meta.insights.length) {
    contentWrap.appendChild(buildInsightBlock("Financial insights", meta.insights));
  }

  if (meta && Array.isArray(meta.recommendations) && meta.recommendations.length) {
    contentWrap.appendChild(buildInsightBlock("Recommendations", meta.recommendations, "recommendations"));
  }
  contentWrap.appendChild(ts);
  row.appendChild(avatar);
  row.appendChild(contentWrap);
  messages.appendChild(row);

  if (window.lucide) lucide.createIcons();
  scrollToBottom();
}

function appendUserMessage(text) {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;

  const row = document.createElement("div");
  row.className = "chatbot-row user";

  const bubble = document.createElement("div");
  bubble.className = "chatbot-bubble user";
  bubble.textContent = text;

  row.appendChild(bubble);
  messages.appendChild(row);
  scrollToBottom();
}

function showTyping() {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;
  if (document.getElementById("typingIndicator")) return;

  const row = document.createElement("div");
  row.className = "chatbot-row bot";
  row.id = "typingIndicator";

  const avatar = document.createElement("div");
  avatar.className = "chatbot-mini-avatar";
  avatar.innerHTML = '<i data-lucide="bot"></i>';

  const bubble = document.createElement("div");
  bubble.className = "chatbot-bubble bot typing";
  bubble.innerHTML = `
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
  `;

  row.appendChild(avatar);
  row.appendChild(bubble);
  messages.appendChild(row);

  if (window.lucide) lucide.createIcons();
  scrollToBottom();
}

function hideTyping() {
  const node = document.getElementById("typingIndicator");
  if (node) node.remove();
}

function renderSuggestedQuestions(questions) {
  clearSuggestions();
  const list = Array.isArray(questions) ? questions.slice(0, 6) : [];
  const messages = document.getElementById("chatMessages");
  if (!messages) return;

  if (!list.length) {
    return;
  }

  const row = document.createElement("div");
  row.className = "chatbot-row bot chatbot-suggestion-row";

  const avatar = document.createElement("div");
  avatar.className = "chatbot-mini-avatar";
  avatar.innerHTML = '<i data-lucide="bot"></i>';

  const box = document.createElement("div");
  box.className = "chatbot-suggestion-box";

  const title = document.createElement("div");
  title.className = "chatbot-suggestions-title";
  title.textContent = "Suggested questions";
  box.appendChild(title);

  const renderItems = (count) => {
    box.querySelectorAll(".chatbot-question-btn, .chatbot-more-btn").forEach((node) => node.remove());
    list.slice(0, count).forEach((question) => {
      const btn = document.createElement("button");
      btn.className = "chatbot-question-btn";
      btn.type = "button";
      btn.innerHTML = `<i data-lucide="${categoryIcon(question.category)}"></i><span>${question.resolved_question}</span>`;
      btn.addEventListener("click", () => handleSuggestedClick(question, btn));
      box.appendChild(btn);
    });

    if (list.length > 3 && count < 6) {
      const moreBtn = document.createElement("button");
      moreBtn.className = "chatbot-more-btn";
      moreBtn.type = "button";
      moreBtn.textContent = "More";
      moreBtn.addEventListener("click", () => {
        renderItems(6);
        if (window.lucide) lucide.createIcons();
        scrollToBottom();
      });
      box.appendChild(moreBtn);
    }
  };

  renderItems(3);

  row.appendChild(avatar);
  row.appendChild(box);
  messages.appendChild(row);

  if (window.lucide) lucide.createIcons();
  scrollToBottom();
}

function renderClarificationOptions(options, templateId) {
  clearSuggestions();
  const messages = document.getElementById("chatMessages");
  if (!messages) return;

  const row = document.createElement("div");
  row.className = "chatbot-row bot chatbot-suggestion-row";

  const avatar = document.createElement("div");
  avatar.className = "chatbot-mini-avatar";
  avatar.innerHTML = '<i data-lucide="bot"></i>';

  const box = document.createElement("div");
  box.className = "chatbot-suggestion-box";

  const title = document.createElement("div");
  title.className = "chatbot-suggestions-title";
  title.textContent = "Which one did you mean?";
  box.appendChild(title);

  (options || []).forEach((option) => {
    const btn = document.createElement("button");
    btn.className = "chatbot-question-btn";
    btn.type = "button";
    btn.innerHTML = `<i data-lucide="help-circle"></i><span>${option}</span>`;
    btn.addEventListener("click", () => handleClarification(templateId, option));
    box.appendChild(btn);
  });

  row.appendChild(avatar);
  row.appendChild(box);
  messages.appendChild(row);

  if (window.lucide) lucide.createIcons();
  scrollToBottom();
}

async function initChatbot() {
  if (chatbotInitialized) return;
  chatbotInitialized = true;

  clearSuggestions();
  showTyping();

  try {
    const res = await fetch(`/api/v1/chatbot/welcome/${chatbotUserId}`, {
      headers: chatbotAuthHeaders,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to initialize chatbot");

    chatbotSessionId = data.session_id;
    hideTyping();
    appendBotMessage(data.welcome_message);
    await sleep(600);
    renderSuggestedQuestions(data.suggested_questions);
  } catch (error) {
    hideTyping();
    appendBotMessage("I could not load your assistant right now. Please try again.");
  }
}

async function handleSuggestedClick(question, button) {
  if (chatbotIsLoading || !chatbotSessionId) return;
  chatbotIsLoading = true;

  if (button) {
    button.classList.add("active");
    setTimeout(() => button.classList.remove("active"), 250);
  }

  appendUserMessage(question.resolved_question);
  clearSuggestions();
  showTyping();

  try {
    const res = await fetch("/api/v1/chatbot/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...chatbotAuthHeaders },
      body: JSON.stringify({
        session_id: chatbotSessionId,
        user_id: chatbotUserId,
        question_type: "suggested",
        template_id: question.template_id,
        entity_value: question.entity_value,
        data_query_type: question.data_query_type,
        resolved_question: question.resolved_question,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to fetch answer");

    hideTyping();
    await sleep(200);
    appendBotMessage(data.answer || "I could not find an answer for that.", data.data || null);
    await sleep(400);
    renderSuggestedQuestions(data.follow_up_questions || []);
  } catch (error) {
    hideTyping();
    appendBotMessage("Something went wrong while getting that answer.");
  } finally {
    chatbotIsLoading = false;
  }
}

async function handleTypedQuestion() {
  const input = document.getElementById("chatInput");
  if (!input || !chatbotSessionId) return;
  const text = input.value.trim();
  if (!text || chatbotIsLoading) return;

  chatbotIsLoading = true;
  input.value = "";
  appendUserMessage(text);
  clearSuggestions();
  showTyping();

  try {
    const res = await fetch("/api/v1/chatbot/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...chatbotAuthHeaders },
      body: JSON.stringify({
        session_id: chatbotSessionId,
        user_id: chatbotUserId,
        question_type: "typed",
        typed_text: text,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to process your question");

    hideTyping();
    if (data.no_match) {
      appendBotMessage(data.message || "I did not understand that question.");
      renderSuggestedQuestions(data.suggested_questions || []);
    } else if (data.needs_clarification) {
      appendBotMessage(data.message || "Please clarify your question.");
      renderClarificationOptions(data.clarification_options || [], data.template_id);
    } else {
      appendBotMessage(data.answer || "I could not find an answer for that.", data.data || null);
      renderSuggestedQuestions(data.follow_up_questions || []);
    }
  } catch (error) {
    hideTyping();
    appendBotMessage("Something went wrong while processing your question.");
  } finally {
    chatbotIsLoading = false;
  }
}

async function handleClarification(templateId, entityValue) {
  if (!templateId || !entityValue || chatbotIsLoading || !chatbotSessionId) return;
  chatbotIsLoading = true;

  appendUserMessage(entityValue);
  clearSuggestions();
  showTyping();

  try {
    const res = await fetch("/api/v1/chatbot/clarify", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...chatbotAuthHeaders },
      body: JSON.stringify({
        session_id: chatbotSessionId,
        user_id: chatbotUserId,
        template_id: templateId,
        entity_value: entityValue,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unable to clarify question");

    hideTyping();
    appendBotMessage(data.answer || "Thanks, I have updated that.", data.data || null);
    renderSuggestedQuestions(data.follow_up_questions || []);
  } catch (error) {
    hideTyping();
    appendBotMessage("I could not process that clarification.");
  } finally {
    chatbotIsLoading = false;
  }
}

function openChatbot() {
  const popup = document.getElementById("chatbotPopup");
  if (!popup) return;

  chatbotIsOpen = !chatbotIsOpen;
  popup.classList.toggle("chatbot-open", chatbotIsOpen);

  if (chatbotIsOpen && !chatbotInitialized) {
    initChatbot();
  }

  if (chatbotIsOpen) {
    const input = document.getElementById("chatInput");
    if (input) input.focus();
  }
}

window.openChatbot = openChatbot;

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSendBtn");
  const btn = document.getElementById("chatbotBtn");

  if (btn) {
    btn.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openChatbot();
      }
    });
  }

  if (input) {
    input.addEventListener("keypress", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleTypedQuestion();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener("click", handleTypedQuestion);
  }
});
