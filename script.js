(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const loginScreen = $('#loginScreen');
  const appShell = $('#appShell');
  const loginForm = $('#loginForm');
  const usernameInput = $('#usernameInput');
  const loginError = $('#loginError');
  const conversation = $('#conversation');
  const messageInput = $('#messageInput');
  const sendButton = $('#sendButton');
  const userList = $('#userList');
  const toast = $('#toast');
  const mobileMenu = $('#mobileMenu');
  const sidebar = $('#sidebar');

  const sampleUsers = [
    { name: 'Maya Chen', color: 'avatar-lavender', role: 'Network Admin' },
    { name: 'Jordan Lee', color: 'avatar-coral', role: 'Student' },
    { name: 'Priya Nair', color: 'avatar-mint', role: 'Student' },
    { name: 'Sam Wilson', color: 'avatar-sand', role: 'Student' },
  ];
  const conversations = new Map();
  let currentUser = '';
  let activeChat = 'group';
  let toastTimer;
  let mockReplyTimer;
  let sessionStartedAt;

  const seedMessages = [
    { kind: 'system', text: 'Welcome to the group. Sample conversation below.' },
    { sender: 'Maya Chen', text: 'Hey everyone! The LAN chat is up and running ✨', time: '09:41', color: 'avatar-lavender' },
    { sender: 'Jordan Lee', text: 'Nice! I can see the group and online users.', time: '09:42', color: 'avatar-coral' },
    { sender: 'Priya Nair', text: 'Messages here are just sample data, but the interface is interactive.', time: '09:43', color: 'avatar-mint' },
  ];
  conversations.set('group', seedMessages);

  function initials(name) {
    return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  }

  function timeNow() {
    return new Intl.DateTimeFormat([], { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2400);
  }

  function getMessages(key = activeChat) {
    if (!conversations.has(key)) conversations.set(key, []);
    return conversations.get(key);
  }

  function renderMessage(message) {
    if (message.kind === 'system') {
      const system = document.createElement('p');
      system.className = 'system-message';
      system.textContent = message.text;
      return system;
    }
    const mine = message.sender === currentUser;
    const row = document.createElement('article');
    row.className = `message-row${mine ? ' mine' : ''}`;
    const avatar = document.createElement('span');
    avatar.className = `avatar message-avatar ${mine ? 'avatar-self' : (message.color || '')}`;
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = initials(message.sender);
    const column = document.createElement('div');
    column.className = 'message-column';
    const meta = document.createElement('div');
    meta.className = 'message-meta';
    const author = document.createElement('strong');
    author.textContent = mine ? 'You' : message.sender;
    const time = document.createElement('time');
    time.textContent = message.time;
    meta.append(author, time);
    if (mine) {
      const sent = document.createElement('span');
      sent.className = 'message-status';
      sent.textContent = '✓ Simulated';
      meta.append(sent);
    }
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = message.text;
    column.append(meta, bubble);
    if (!mine) row.append(avatar);
    row.append(column);
    return row;
  }

  function renderConversation() {
    conversation.replaceChildren();
    const divider = document.createElement('div');
    divider.className = 'day-divider';
    divider.textContent = 'TODAY';
    conversation.append(divider);
    getMessages().forEach((message) => conversation.append(renderMessage(message)));
    conversation.scrollTop = conversation.scrollHeight;
  }

  function renderUsers() {
    userList.replaceChildren();
    const everyone = [...sampleUsers, { name: currentUser, color: 'avatar-self', role: 'You' }];
    $('#onlineCount').textContent = String(everyone.length);
    $('#metaText').textContent = `${everyone.length} people online`;
    everyone.forEach((person) => {
      if (person.name === currentUser) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `person-button${activeChat === person.name ? ' selected' : ''}`;
      button.setAttribute('aria-label', `Open private chat with ${person.name}`);
      const avatar = document.createElement('span');
      avatar.className = `avatar ${person.color}`;
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = initials(person.name);
      const copy = document.createElement('span');
      copy.className = 'person-copy';
      const name = document.createElement('strong');
      name.textContent = person.name;
      const role = document.createElement('small');
      role.textContent = person.role;
      const status = document.createElement('span');
      status.className = 'person-status';
      status.setAttribute('aria-label', 'Online');
      copy.append(name, role);
      button.append(avatar, copy, status);
      button.addEventListener('click', () => openPrivateChat(person.name));
      userList.append(button);
    });
  }

  function openPrivateChat(name) {
    activeChat = name;
    $('#chatTitle').textContent = name;
    $('#chatSubtitle').textContent = 'Private conversation · only you and this person';
    $('#headingIcon').textContent = initials(name).slice(0, 1);
    $('#headingIcon').className = 'chat-heading-icon';
    $('#groupChatButton').classList.remove('active');
    renderUsers();
    renderConversation();
    sidebar.classList.remove('mobile-open');
    mobileMenu.setAttribute('aria-expanded', 'false');
    messageInput.placeholder = `Message ${name}…`;
    messageInput.focus();
  }

  function openGroupChat() {
    activeChat = 'group';
    $('#chatTitle').textContent = 'Group Chat';
    $('#chatSubtitle').textContent = 'Messages are visible to everyone online';
    $('#headingIcon').textContent = '#';
    $('#headingIcon').className = 'chat-heading-icon';
    $('#groupChatButton').classList.add('active');
    $('#groupUnread').classList.add('is-hidden');
    renderUsers();
    renderConversation();
    sidebar.classList.remove('mobile-open');
    mobileMenu.setAttribute('aria-expanded', 'false');
    messageInput.placeholder = 'Write a message…';
    messageInput.focus();
  }

  function addMockPrivateReply(name) {
    if (activeChat !== name || !appShell.isConnected || appShell.classList.contains('is-hidden')) return;
    const replies = [
      'Thanks for the message! 👋',
      'Good point — glad we can chat here.',
      'I can see your message in this browser preview 🙂',
      'Sounds good! This is a simulated reply.',
    ];
    getMessages(name).push({ sender: name, text: replies[Math.floor(Math.random() * replies.length)], time: timeNow(), color: sampleUsers.find((user) => user.name === name)?.color });
    renderConversation();
  }

  function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) {
      showToast('Type a message before sending.');
      messageInput.focus();
      return;
    }
    if (text.length > 2000) {
      showToast('Messages can be up to 2,000 characters.');
      return;
    }
    getMessages().push({ sender: currentUser, text, time: timeNow() });
    messageInput.value = '';
    messageInput.style.height = 'auto';
    renderConversation();
    if (activeChat !== 'group') {
      const recipient = activeChat;
      clearTimeout(mockReplyTimer);
      mockReplyTimer = setTimeout(() => addMockPrivateReply(recipient), 1100);
    } else {
      showToast('Message added to the browser simulation.');
    }
  }

  function startSession(name) {
    currentUser = name.trim();
    sessionStartedAt = Date.now();
    conversations.clear();
    conversations.set('group', [...seedMessages]);
    conversations.set('Maya Chen', [
      { kind: 'system', text: 'Private browser preview with Maya Chen.' },
      { sender: 'Maya Chen', text: 'Hi! Feel free to send a message. I’ll reply with a simulated response.', time: '09:40', color: 'avatar-lavender' },
    ]);
    conversations.set('Jordan Lee', [
      { kind: 'system', text: 'Private browser preview with Jordan Lee.' },
      { sender: 'Jordan Lee', text: 'Hey! This private chat is only a browser-side preview.', time: '09:38', color: 'avatar-coral' },
    ]);
    conversations.set('Priya Nair', [
      { kind: 'system', text: 'Private browser preview with Priya Nair.' },
      { sender: 'Priya Nair', text: 'Hello there 👋 The reply you receive will be simulated.', time: '09:37', color: 'avatar-mint' },
    ]);
    conversations.set('Sam Wilson', [
      { kind: 'system', text: 'Private browser preview with Sam Wilson.' },
      { sender: 'Sam Wilson', text: 'Welcome! Try sending a message to see the simulated interaction.', time: '09:35', color: 'avatar-sand' },
    ]);
    loginScreen.classList.add('is-hidden');
    appShell.classList.remove('is-hidden');
    $('#profileName').textContent = currentUser;
    $('#profileAvatar').textContent = initials(currentUser);
    activeChat = 'group';
    openGroupChat();
    renderConversation();
    showToast(`Welcome, ${currentUser}. This is a simulated session.`);
  }

  loginForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const name = usernameInput.value.trim();
    if (!name) {
      loginError.textContent = 'Please enter a display name to continue.';
      usernameInput.focus();
      return;
    }
    if (name.length > 20 || !/^[A-Za-z0-9 _-]+$/.test(name)) {
      loginError.textContent = 'Use 1–20 letters, numbers, spaces, underscores, or hyphens.';
      usernameInput.focus();
      return;
    }
    loginError.textContent = '';
    startSession(name);
  });

  $('#groupChatButton').addEventListener('click', openGroupChat);
  sendButton.addEventListener('click', sendMessage);
  messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
  });
  messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
  $('#disconnectButton').addEventListener('click', () => {
    clearTimeout(mockReplyTimer);
    appShell.classList.add('is-hidden');
    loginScreen.classList.remove('is-hidden');
    loginError.textContent = '';
    usernameInput.value = '';
    usernameInput.focus();
    const duration = Math.max(1, Math.round((Date.now() - sessionStartedAt) / 1000));
    showToast(`Browser session ended after ${duration}s.`);
  });
  $('#profileButton').addEventListener('click', () => showToast(`Signed in as ${currentUser} for this browser session.`));
  mobileMenu.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('mobile-open');
    mobileMenu.setAttribute('aria-expanded', String(isOpen));
  });
  document.addEventListener('click', (event) => {
    if (!sidebar.contains(event.target) && !mobileMenu.contains(event.target) && sidebar.classList.contains('mobile-open')) {
      sidebar.classList.remove('mobile-open');
      mobileMenu.setAttribute('aria-expanded', 'false');
    }
  });
  window.addEventListener('resize', () => {
    if (window.innerWidth > 560) {
      sidebar.classList.remove('mobile-open');
      mobileMenu.setAttribute('aria-expanded', 'false');
    }
  });

})();
