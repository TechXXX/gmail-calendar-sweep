const CONFIG = {
  baseSearchQuery:
    'in:anywhere -in:chats',
  searchWindows: [
    {label: '0-30d', query: 'newer_than:30d', maxThreads: 200},
    {label: '31-60d', query: 'older_than:30d newer_than:60d', maxThreads: 200},
    {label: '61-90d', query: 'older_than:60d newer_than:90d', maxThreads: 200},
    {label: '91-120d', query: 'older_than:90d newer_than:120d', maxThreads: 200}
  ],
  maxMessagesPerThread: 10,
  maxBodyLength: 12000,
  candidateSheetName: 'Email Event Candidates',
  summarySheetName: 'Category Summary',
  propertyPrefix: 'gmailCalendarSweep',
  batchSize: 40,
  minConfidence: 3,
  strongSenderPatterns: [
    /airlines?/i,
    /lufthansa/i,
    /klm/i,
    /thai/i,
    /booking\.com/i,
    /hotel/i,
    /airbnb/i,
    /uber/i,
    /grab/i,
    /ryanair/i,
    /easyjet/i,
    /expedia/i,
    /trip/i,
    /rail/i,
    /doctor/i,
    /hospital/i,
    /clinic/i,
    /eventbrite/i,
    /ticketmaster/i
  ],
  futureSignals: [
    'tomorrow',
    'today',
    'upcoming',
    'scheduled for',
    'see you on',
    'starts at',
    'starting at',
    'boarding',
    'check-in',
    'check in',
    'departs',
    'departure',
    'arrives',
    'arrival',
    'pickup at',
    'pick up at',
    'reservation for',
    'appointment on',
    'appointment at',
    'your flight to',
    'your trip to',
    'join us on'
  ],
  negativeSenderPatterns: [
    /substack/i,
    /glassdoor/i,
    /linkedin/i,
    /paypal/i,
    /apple/i,
    /compass24/i
  ],
  negativeSubjectPatterns: [
    /\binvoice\b/i,
    /\breceipt\b/i,
    /\be-?receipt\b/i,
    /\bpayment\b/i,
    /\bcommunity\b/i,
    /\bdigest\b/i,
    /\bnewsletter\b/i,
    /\bnews round/i,
    /\bsubstack\b/i
  ],
  negativeBodyPatterns: [
    /\bread more\b/i,
    /\bcomments\b/i,
    /\breader-supported\b/i,
    /\bnewsletter\b/i,
    /\bsubscribe\b/i,
    /\bprivacy policy\b/i,
    /\bterms of service\b/i
  ],
  subjectConfidencePatterns: [
    /\bconfirm(?:ed)?\b/i,
    /\breminder\b/i,
    /\breservation\b/i,
    /\bbooking\b/i,
    /\bticket\b/i,
    /\bboarding\b/i,
    /\bcheck-?in\b/i,
    /\bappointment\b/i
  ],
  categories: [
    {
      name: 'travel',
      keywords: [
        'flight',
        'boarding',
        'check-in',
        'check in',
        'departure',
        'arrival',
        'terminal',
        'hotel',
        'reservation',
        'booking',
        'itinerary',
        'rental car',
        'trip',
        'departs',
        'arrives'
      ]
    },
    {
      name: 'appointment',
      keywords: [
        'appointment',
        'scheduled',
        'consultation',
        'meeting',
        'interview',
        'doctor',
        'dentist',
        'haircut',
        'service appointment',
        'confirmed appointment'
      ]
    },
    {
      name: 'event',
      keywords: [
        'ticket',
        'event',
        'concert',
        'conference',
        'webinar',
        'workshop',
        'meetup',
        'festival',
        'admission',
        'join us on'
      ]
    },
    {
      name: 'deadline',
      keywords: [
        'deadline',
        'due date',
        'payment due',
        'renewal',
        'expires',
        'expiration',
        'respond by',
        'submit by',
        'last day'
      ]
    },
    {
      name: 'delivery',
      keywords: [
        'delivery',
        'arriving',
        'pickup',
        'collection',
        'drop-off',
        'drop off',
        'window',
        'courier'
      ]
    }
  ],
  datePatterns: [
    /\b(?:mon|monday|tue|tuesday|wed|wednesday|thu|thursday|fri|friday|sat|saturday|sun|sunday),?\s+(\d{1,2})\s+(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+(\d{4})\b/gi,
    /\b(\d{1,2})\s+(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+(\d{4})\b/gi,
    /\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+(\d{1,2}),?\s+(\d{4})\b/gi,
    /\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b/g
  ],
  timePatterns: [
    /\b([01]?\d|2[0-3]):([0-5]\d)\b/g,
    /\b([1-9]|1[0-2])(?::([0-5]\d))?\s?(am|pm)\b/gi
  ]
};

function runBroadEmailCalendarSweep() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  if (!spreadsheet) {
    throw new Error('Open this project from a Google Sheet and run it there, or bind the script to a Sheet first.');
  }

  const candidateSheet = getOrCreateSheet_(spreadsheet, CONFIG.candidateSheetName);
  const summarySheet = getOrCreateSheet_(spreadsheet, CONFIG.summarySheetName);
  const state = getSweepState_();
  const startedAt = new Date();

  if (!state.initialized) {
    initializeSweepSheets_(candidateSheet, summarySheet, startedAt);
    state.initialized = true;
  }

  const windowConfig = CONFIG.searchWindows[state.windowIndex];
  if (!windowConfig) {
    finalizeSweep_(candidateSheet, summarySheet, state, startedAt);
    return;
  }

  const query = CONFIG.baseSearchQuery + ' ' + windowConfig.query;
  const threads = GmailApp.search(query, state.threadOffset, CONFIG.batchSize);
  const rows = [];

  threads.forEach(function(thread) {
    const messages = thread.getMessages().slice(0, CONFIG.maxMessagesPerThread);
    messages.forEach(function(message) {
      if (state.seenMessageIds[message.getId()]) {
        return;
      }

      const candidate = inspectMessage_(message);
      if (!candidate) {
        return;
      }

      state.seenMessageIds[message.getId()] = true;
      rows.push(candidateToRow_(candidate));
    });
  });

  appendCandidateRows_(candidateSheet, rows);

  if (threads.length < CONFIG.batchSize || state.threadOffset + CONFIG.batchSize >= windowConfig.maxThreads) {
    state.windowIndex += 1;
    state.threadOffset = 0;
  } else {
    state.threadOffset += CONFIG.batchSize;
  }

  state.lastRunAt = startedAt.toISOString();
  saveSweepState_(state);
  writeSummaryFromCandidateSheet_(summarySheet, candidateSheet, state, startedAt);
}

function previewTopCandidates() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(CONFIG.candidateSheetName);

  if (!sheet) {
    Logger.log('No candidate sheet found yet.');
    return;
  }

  const values = sheet.getDataRange().getValues();
  const header = values.shift();
  const topRows = values
    .filter(function(row) {
      return row[2] >= 4;
    })
    .slice(0, 20);

  Logger.log(JSON.stringify({header: header, rows: topRows}, null, 2));
}

function resetBroadEmailCalendarSweep() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  if (!spreadsheet) {
    throw new Error('Open this project from a Google Sheet and run it there, or bind the script to a Sheet first.');
  }

  initializeSweepSheets_(
    getOrCreateSheet_(spreadsheet, CONFIG.candidateSheetName),
    getOrCreateSheet_(spreadsheet, CONFIG.summarySheetName),
    new Date()
  );
  clearSweepState_();
}

function inspectMessage_(message) {
  const rawSubject = message.getSubject();
  const rawFrom = message.getFrom();
  const subject = safeLower_(rawSubject);
  const plainBody = truncate_(safeLower_(message.getPlainBody()), CONFIG.maxBodyLength);
  const from = safeLower_(rawFrom);
  const text = [subject, plainBody].join('\n');

  if (isNegativeCandidate_(rawFrom, rawSubject, plainBody)) {
    return null;
  }

  const keywordMatches = detectKeywordMatches_(text);
  const hasStrongSender = matchesAny_(rawFrom, CONFIG.strongSenderPatterns);
  const hasFutureSignal = containsAnyPhrase_(text, CONFIG.futureSignals);
  const hasStrongSubject = matchesAny_(rawSubject, CONFIG.subjectConfidencePatterns);
  const allowDateFallback =
    (hasStrongSender && hasFutureSignal) ||
    (hasStrongSender && message.getAttachments().length > 0) ||
    (hasStrongSender && hasStrongSubject);
  const dateMatch = detectDate_(text, allowDateFallback ? message.getDate() : null);
  const timeMatch = detectTime_(text);
  const confidence = scoreCandidate_(
    keywordMatches,
    dateMatch,
    timeMatch,
    message,
    hasStrongSender,
    hasFutureSignal,
    hasStrongSubject
  );

  if (!dateMatch || confidence < CONFIG.minConfidence) {
    return null;
  }

  const category = keywordMatches.bestCategory || 'uncategorized';
  const reasonParts = [];
  if (keywordMatches.matchedKeywords.length) {
    reasonParts.push('keywords: ' + keywordMatches.matchedKeywords.slice(0, 5).join(', '));
  }
  if (dateMatch.raw) {
    reasonParts.push('date: ' + dateMatch.raw);
  }
  if (timeMatch && timeMatch.raw) {
    reasonParts.push('time: ' + timeMatch.raw);
  }
  if (message.getAttachments().length) {
    reasonParts.push('attachments present');
  }

  return {
    scanTimestamp: new Date(),
    category: category,
    confidence: confidence,
    sender: flattenText_(message.getFrom()),
    subject: flattenText_(message.getSubject()),
    detectedDate: dateMatch.isoDate,
    detectedTime: timeMatch ? timeMatch.normalized : '',
    eventType: inferEventType_(category, keywordMatches.matchedKeywords),
    reason: flattenText_(reasonParts.join(' | ')),
    gmailLink: 'https://mail.google.com/mail/u/0/#inbox/' + message.getId(),
    threadId: message.getThread().getId(),
    messageId: message.getId(),
    messageDate: message.getDate(),
    hasAttachment: message.getAttachments().length > 0,
    snippet: buildSnippet_(from, subject, plainBody, keywordMatches.matchedKeywords)
  };
}

function detectKeywordMatches_(text) {
  const matchedKeywords = [];
  const categoryScores = {};

  CONFIG.categories.forEach(function(category) {
    category.keywords.forEach(function(keyword) {
      if (text.indexOf(keyword) !== -1) {
        matchedKeywords.push(keyword);
        categoryScores[category.name] = (categoryScores[category.name] || 0) + 1;
      }
    });
  });

  let bestCategory = '';
  let bestScore = 0;
  Object.keys(categoryScores).forEach(function(categoryName) {
    if (categoryScores[categoryName] > bestScore) {
      bestCategory = categoryName;
      bestScore = categoryScores[categoryName];
    }
  });

  return {
    bestCategory: bestCategory,
    matchedKeywords: matchedKeywords,
    categoryScores: categoryScores
  };
}

function detectDate_(text, fallbackDate) {
  for (let i = 0; i < CONFIG.datePatterns.length; i += 1) {
    const regex = new RegExp(CONFIG.datePatterns[i]);
    const match = regex.exec(text);
    if (!match) {
      continue;
    }

    const parsed = parseDateMatch_(match);
    if (!parsed) {
      continue;
    }

    return {
      raw: match[0],
      isoDate: Utilities.formatDate(parsed, Session.getScriptTimeZone(), 'yyyy-MM-dd')
    };
  }

  if (fallbackDate) {
    return {
      raw: 'message-date fallback',
      isoDate: Utilities.formatDate(fallbackDate, Session.getScriptTimeZone(), 'yyyy-MM-dd')
    };
  }

  return null;
}

function parseDateMatch_(match) {
  if (match.length === 4 && isNaN(Number(match[2]))) {
    return buildDateFromParts_(Number(match[1]), monthIndex_(match[2]), normalizeYear_(match[3]));
  }

  if (match.length === 4 && isNaN(Number(match[1]))) {
    return buildDateFromParts_(Number(match[2]), monthIndex_(match[1]), normalizeYear_(match[3]));
  }

  if (match.length === 4) {
    const day = Number(match[1]);
    const month = Number(match[2]) - 1;
    const year = normalizeYear_(match[3]);
    return buildDateFromParts_(day, month, year);
  }

  return null;
}

function detectTime_(text) {
  for (let i = 0; i < CONFIG.timePatterns.length; i += 1) {
    const regex = new RegExp(CONFIG.timePatterns[i]);
    const match = regex.exec(text);
    if (!match) {
      continue;
    }

    return {
      raw: match[0],
      normalized: normalizeTimeMatch_(match)
    };
  }

  return null;
}

function normalizeTimeMatch_(match) {
  if (match[3]) {
    let hours = Number(match[1]);
    const minutes = match[2] ? Number(match[2]) : 0;
    const meridiem = match[3].toLowerCase();

    if (meridiem === 'pm' && hours !== 12) {
      hours += 12;
    } else if (meridiem === 'am' && hours === 12) {
      hours = 0;
    }

    return pad2_(hours) + ':' + pad2_(minutes);
  }

  return pad2_(Number(match[1])) + ':' + pad2_(Number(match[2]));
}

function scoreCandidate_(keywordMatches, dateMatch, timeMatch, message, hasStrongSender, hasFutureSignal, hasStrongSubject) {
  let score = 0;

  score += Math.min(keywordMatches.matchedKeywords.length, 2);
  if (dateMatch && dateMatch.raw !== 'message-date fallback') {
    score += 2;
  }
  if (timeMatch) {
    score += 1;
  }
  if (message.getAttachments().length > 0) {
    score += 1;
  }
  if (/\b(confirm|confirmed|reminder|receipt|reservation|ticket)\b/.test(safeLower_(message.getSubject()))) {
    score += 1;
  }
  if (hasStrongSender) {
    score += 2;
  }
  if (hasFutureSignal) {
    score += 2;
  }
  if (hasStrongSubject) {
    score += 1;
  }
  if (dateMatch && dateMatch.raw === 'message-date fallback') {
    score -= 1;
  }

  return score;
}

function inferEventType_(category, matchedKeywords) {
  if (matchedKeywords.indexOf('boarding') !== -1) {
    return 'boarding';
  }
  if (matchedKeywords.indexOf('check-in') !== -1 || matchedKeywords.indexOf('check in') !== -1) {
    return 'check-in';
  }
  if (matchedKeywords.indexOf('appointment') !== -1) {
    return 'appointment';
  }
  if (matchedKeywords.indexOf('deadline') !== -1 || matchedKeywords.indexOf('due date') !== -1) {
    return 'deadline';
  }
  if (matchedKeywords.indexOf('delivery') !== -1 || matchedKeywords.indexOf('pickup') !== -1) {
    return 'delivery window';
  }

  return category;
}

function buildSnippet_(from, subject, body, matchedKeywords) {
  const context = matchedKeywords.length ? matchedKeywords[0] : '';
  const bodySnippet = context ? extractWindow_(body, context, 120) : body.slice(0, 120);
  return flattenText_([from, subject, bodySnippet].filter(Boolean).join(' | '));
}

function extractWindow_(text, keyword, radius) {
  const index = text.indexOf(keyword);
  if (index === -1) {
    return text.slice(0, radius);
  }

  const start = Math.max(0, index - Math.floor(radius / 2));
  const end = Math.min(text.length, index + Math.floor(radius / 2));
  return text.slice(start, end).replace(/\s+/g, ' ').trim();
}

function writeCandidateRows_(sheet, rows, startedAt) {
  const header = [
    'scan_timestamp',
    'category',
    'confidence',
    'sender',
    'subject',
    'detected_date',
    'detected_time',
    'event_type',
    'reason',
    'gmail_link',
    'thread_id',
    'message_id',
    'message_date',
    'has_attachment',
    'snippet'
  ];

  sheet.clear();
  sheet.getRange(1, 1, 1, header.length).setValues([header]);

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, header.length).setValues(rows);
    sheet.getRange(2, 1, rows.length, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
    sheet.getRange(2, 6, rows.length, 1).setNumberFormat('yyyy-mm-dd');
    sheet.getRange(2, 13, rows.length, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  }

  sheet.autoResizeColumns(1, header.length);
  sheet.setFrozenRows(1);
}

function writeSummary_(sheet, summary, totalRows, startedAt) {
  const header = ['category', 'candidate_count', 'high_confidence_count'];
  const rows = Object.keys(summary)
    .sort()
    .map(function(category) {
      return [category, summary[category].count, summary[category].highConfidence];
    });

  sheet.clear();
  sheet.getRange(1, 1, 1, header.length).setValues([header]);

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, header.length).setValues(rows);
  }

  sheet.getRange('E1').setValue('Last scan started');
  sheet.getRange('E2').setValue(startedAt);
  sheet.getRange('E2').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('F1').setValue('Total candidates');
  sheet.getRange('F2').setValue(totalRows);
  sheet.getRange('G1').setValue('Status');
  sheet.getRange('G2').setValue('Running');
  sheet.autoResizeColumns(1, 8);
  sheet.setFrozenRows(1);
}

function initializeSweepSheets_(candidateSheet, summarySheet, startedAt) {
  writeCandidateRows_(candidateSheet, [], startedAt);
  writeSummary_(summarySheet, {}, 0, startedAt);
}

function appendCandidateRows_(sheet, rows) {
  if (!rows.length) {
    return;
  }

  const startRow = Math.max(sheet.getLastRow() + 1, 2);
  sheet.getRange(startRow, 1, rows.length, rows[0].length).setValues(rows);
  sheet.getRange(startRow, 1, rows.length, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange(startRow, 6, rows.length, 1).setNumberFormat('yyyy-mm-dd');
  sheet.getRange(startRow, 13, rows.length, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
}

function writeSummaryFromCandidateSheet_(summarySheet, candidateSheet, state, startedAt) {
  const values = candidateSheet.getDataRange().getValues();
  const rows = values.slice(1).filter(function(row) {
    return row[0];
  });
  const summary = {};

  rows.forEach(function(row) {
    const category = row[1] || 'uncategorized';
    const confidence = Number(row[2] || 0);
    summary[category] = summary[category] || {count: 0, highConfidence: 0};
    summary[category].count += 1;
    if (confidence >= 4) {
      summary[category].highConfidence += 1;
    }
  });

  writeSummary_(summarySheet, summary, rows.length, startedAt);
  summarySheet.getRange('H1').setValue('Progress');
  summarySheet.getRange('H2').setValue(buildProgressLabel_(state));
}

function candidateToRow_(candidate) {
  return [
    candidate.scanTimestamp,
    candidate.category,
    candidate.confidence,
    candidate.sender,
    candidate.subject,
    candidate.detectedDate,
    candidate.detectedTime,
    candidate.eventType,
    candidate.reason,
    candidate.gmailLink,
    candidate.threadId,
    candidate.messageId,
    candidate.messageDate,
    candidate.hasAttachment,
    candidate.snippet
  ];
}

function getSweepState_() {
  const properties = PropertiesService.getScriptProperties();
  const raw = properties.getProperty(CONFIG.propertyPrefix + '.state');

  if (!raw) {
    return {
      initialized: false,
      windowIndex: 0,
      threadOffset: 0,
      seenMessageIds: {},
      lastRunAt: ''
    };
  }

  const parsed = JSON.parse(raw);
  parsed.seenMessageIds = parsed.seenMessageIds || {};
  return parsed;
}

function saveSweepState_(state) {
  PropertiesService.getScriptProperties().setProperty(
    CONFIG.propertyPrefix + '.state',
    JSON.stringify(state)
  );
}

function clearSweepState_() {
  PropertiesService.getScriptProperties().deleteProperty(CONFIG.propertyPrefix + '.state');
}

function finalizeSweep_(candidateSheet, summarySheet, state, startedAt) {
  writeSummaryFromCandidateSheet_(summarySheet, candidateSheet, state, startedAt);
  summarySheet.getRange('G2').setValue('Completed');
  summarySheet.getRange('H2').setValue('Completed');
  clearSweepState_();
}

function buildProgressLabel_(state) {
  if (state.windowIndex >= CONFIG.searchWindows.length) {
    return 'Completed';
  }

  return (
    CONFIG.searchWindows[state.windowIndex].label +
    ' offset ' +
    state.threadOffset
  );
}

function getOrCreateSheet_(spreadsheet, name) {
  return spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
}

function isNegativeCandidate_(from, subject, body) {
  return (
    matchesAny_(from, CONFIG.negativeSenderPatterns) ||
    matchesAny_(subject, CONFIG.negativeSubjectPatterns) ||
    matchesAny_(body, CONFIG.negativeBodyPatterns)
  );
}

function matchesAny_(value, patterns) {
  return patterns.some(function(pattern) {
    return pattern.test(String(value || ''));
  });
}

function containsAnyPhrase_(text, phrases) {
  return phrases.some(function(phrase) {
    return text.indexOf(phrase) !== -1;
  });
}

function flattenText_(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildDateFromParts_(day, monthIndex, year) {
  if (
    !Number.isFinite(day) ||
    !Number.isFinite(monthIndex) ||
    !Number.isFinite(year) ||
    monthIndex < 0 ||
    monthIndex > 11
  ) {
    return null;
  }

  const date = new Date(year, monthIndex, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== monthIndex ||
    date.getDate() !== day
  ) {
    return null;
  }

  return date;
}

function monthIndex_(value) {
  const months = {
    jan: 0,
    january: 0,
    feb: 1,
    february: 1,
    mar: 2,
    march: 2,
    apr: 3,
    april: 3,
    may: 4,
    jun: 5,
    june: 5,
    jul: 6,
    july: 6,
    aug: 7,
    august: 7,
    sep: 8,
    sept: 8,
    september: 8,
    oct: 9,
    october: 9,
    nov: 10,
    november: 10,
    dec: 11,
    december: 11
  };

  return months[safeLower_(value)];
}

function normalizeYear_(value) {
  const numeric = Number(value);
  if (numeric < 100) {
    return numeric >= 70 ? 1900 + numeric : 2000 + numeric;
  }
  return numeric;
}

function safeLower_(value) {
  return String(value || '').toLowerCase();
}

function truncate_(value, maxLength) {
  return value.length > maxLength ? value.slice(0, maxLength) : value;
}

function pad2_(value) {
  return value < 10 ? '0' + value : String(value);
}
