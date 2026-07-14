# Groq API Integration Guide for Node.js (2026)

---

# 1. What is Groq?

Groq provides OpenAI-compatible APIs for running ultra-fast LLM inference.

Popular models include:

```text
llama-4
llama-3.3-70b
llama-3.1-8b
deepseek-r1-distill-llama
qwen-qwq-32b
gemma-2
```

For most applications:

```text
Chatbot
↓
Llama 3.3 70B

Reasoning
↓
DeepSeek R1

Fast Responses
↓
Llama 3.1 8B
```

---

# 2. Create Groq Account

Visit:

```text
https://console.groq.com
```

Sign in using:

```text
Google
GitHub
Email
```

---

# 3. Generate API Key

Navigate:

```text
Dashboard
    ↓
API Keys
    ↓
Create API Key
```

Example:

```text
gsk_xxxxxxxxxxxxxxxxxxxxxxxxx
```

Store securely.

Never expose it in frontend code.

---

# 4. Create Node Project

```bash
mkdir groq-test

cd groq-test

npm init -y
```

---

# 5. Install Dependencies

Official SDK:

```bash
npm install groq-sdk
```

Environment variables:

```bash
npm install dotenv
```

Express backend:

```bash
npm install express cors
```

---

# 6. Project Structure

```text
project
│
├── server.js
├── .env
├── package.json
│
├── routes
│   └── chat.js
│
├── services
│   └── groq.js
│
└── controllers
    └── chatController.js
```

---

# 7. Configure Environment Variables

Create:

```text
.env
```

Add:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxx
PORT=5000
```

---

# 8. Initialize Groq Client

Create:

```text
services/groq.js
```

```javascript
const Groq = require("groq-sdk");

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

module.exports = groq;
```

---

# 9. Simple Chat Completion

Create:

```javascript
const Groq = require("groq-sdk");

require("dotenv").config();

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

async function main() {
  const completion =
    await groq.chat.completions.create({
      messages: [
        {
          role: "user",
          content: "Explain recursion"
        }
      ],
      model: "llama-3.3-70b-versatile"
    });

  console.log(
    completion.choices[0].message.content
  );
}

main();
```

Run:

```bash
node index.js
```

---

# 10. Response Structure

Groq returns:

```json
{
  "id": "...",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "..."
      }
    }
  ]
}
```

Extract:

```javascript
completion.choices[0].message.content
```

---

# 11. Express Integration

## server.js

```javascript
require("dotenv").config();

const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());

app.use("/api/chat", require("./routes/chat"));

app.listen(5000, () => {
  console.log("Server Running");
});
```

---

## routes/chat.js

```javascript
const router = require("express").Router();

const {
  chatController
} = require("../controllers/chatController");

router.post("/", chatController);

module.exports = router;
```

---

## controllers/chatController.js

```javascript
const groq = require("../services/groq");

exports.chatController = async (
  req,
  res
) => {
  try {
    const { message } = req.body;

    const response =
      await groq.chat.completions.create({
        model:
          "llama-3.3-70b-versatile",

        messages: [
          {
            role: "user",
            content: message
          }
        ]
      });

    res.json({
      success: true,
      response:
        response.choices[0]
          .message.content
    });
  } catch (error) {
    console.error(error);

    res.status(500).json({
      success: false
    });
  }
};
```

---

# 12. API Testing

POST:

```http
http://localhost:5000/api/chat
```

Body:

```json
{
  "message": "Tell me a joke"
}
```

Response:

```json
{
  "success": true,
  "response": "..."
}
```

---

# 13. System Prompts

```javascript
messages: [
  {
    role: "system",
    content:
      "You are a music therapist."
  },
  {
    role: "user",
    content:
      "I feel stressed"
  }
]
```

---

# 14. Multi-turn Conversations

```javascript
messages: [
  {
    role: "system",
    content:
      "You are helpful"
  },

  {
    role: "user",
    content:
      "Who is Einstein?"
  },

  {
    role: "assistant",
    content:
      "Einstein was..."
  },

  {
    role: "user",
    content:
      "When was he born?"
  }
]
```

---

# 15. Temperature

Controls creativity.

```javascript
temperature: 0
```

```text
Deterministic
```

---

```javascript
temperature: 0.7
```

```text
Balanced
```

---

```javascript
temperature: 1.2
```

```text
Creative
```

---

# 16. Max Tokens

Limits output size.

```javascript
max_completion_tokens: 1000
```

Example:

```javascript
await groq.chat.completions.create({
  model:
    "llama-3.3-70b-versatile",

  messages,

  max_completion_tokens: 1000
});
```

---

# 17. Streaming Responses

Useful for ChatGPT-style typing.

```javascript
const stream =
await groq.chat.completions.create({
  messages,
  model:
    "llama-3.3-70b-versatile",
  stream: true
});
```

Read chunks:

```javascript
for await (
  const chunk of stream
) {
  process.stdout.write(
    chunk.choices[0]?.delta?.content || ""
  );
}
```

---

# 18. Express Streaming Endpoint

```javascript
router.post(
  "/stream",
  async (req, res) => {
    const stream =
      await groq.chat.completions.create({
        model:
          "llama-3.3-70b-versatile",

        messages:
          req.body.messages,

        stream: true
      });

    res.setHeader(
      "Content-Type",
      "text/plain"
    );

    for await (
      const chunk of stream
    ) {
      res.write(
        chunk.choices[0]?.delta
          ?.content || ""
      );
    }

    res.end();
  }
);
```

---

# 19. JSON Output Mode

Structured responses.

```javascript
const response =
await groq.chat.completions.create({
  model:
    "llama-3.3-70b-versatile",

  response_format: {
    type: "json_object"
  },

  messages
});
```

Example output:

```json
{
  "mood": "sad",
  "confidence": 0.92
}
```

---

# 20. Tool Calling

Groq supports OpenAI-style tool calls.

Example:

```javascript
tools: [
  {
    type: "function",
    function: {
      name: "searchSongs",
      description:
        "Search songs",

      parameters: {
        type: "object",
        properties: {
          mood: {
            type: "string"
          }
        }
      }
    }
  }
]
```

Workflow:

```text
User Message
     ↓
Model
     ↓
Tool Call
     ↓
Backend Function
     ↓
Tool Result
     ↓
Final Response
```

---

# 21. Error Handling

```javascript
try {
   ...
}
catch(error){

   console.error(error);

   if(error.status===429){
      console.log(
        "Rate Limit"
      );
   }

   if(error.status===401){
      console.log(
        "Invalid Key"
      );
   }
}
```

---

# 22. Common Errors

### Invalid Key

```text
401 Unauthorized
```

Cause:

```text
Wrong API Key
```

---

### Rate Limited

```text
429 Too Many Requests
```

Cause:

```text
Too many requests
```

---

### Model Not Found

```text
404 Model Not Found
```

Cause:

```text
Incorrect model name
```

---

# 23. Production Best Practices

```text
Frontend
    ↓
Express Backend
    ↓
Groq API
```

Never:

```text
Frontend
    ↓
Groq API
```

Reason:

```text
API Key Exposure
```

---

# 24. Recommended Architecture for Moodify

```text
User Mood Input
        ↓
React Frontend
        ↓
Express Backend
        ↓
Groq Llama 3.3 70B
        ↓
Mood Analysis
        ↓
Generate Search Queries
        ↓
YouTube Search API
        ↓
Playlist Candidates
        ↓
Return Recommendations
```

---

# 25. Recommended Models

| Use Case                   | Model                         |
| -------------------------- | ----------------------------- |
| General Chat               | llama-3.3-70b-versatile       |
| Fast Responses             | llama-3.1-8b-instant          |
| Reasoning                  | deepseek-r1-distill-llama-70b |
| Coding                     | llama-3.3-70b-versatile       |
| Mood Analysis              | llama-3.3-70b-versatile       |
| Therapy-style Conversation | llama-3.3-70b-versatile       |

---

# 26. Complete Production Flow

```text
User Message
      ↓
Frontend
      ↓
POST /api/chat
      ↓
Express Controller
      ↓
Groq SDK
      ↓
Groq Model
      ↓
Structured Mood Analysis
      ↓
YouTube Query Generation
      ↓
YouTube Search API
      ↓
Rank Results
      ↓
Return Playlist + AI Response
```

This architecture is ideal for your **Moodify** application because Groq handles the conversational and mood-analysis layer, while YouTube provides the music catalog and playback layer.
