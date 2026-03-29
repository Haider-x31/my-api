const express = require("express");
const fetch = require("node-fetch");
const app = express();

app.use(express.json());

app.post("/download", async (req, res) => {
  const { url } = req.body;

  try {
    const response = await fetch(`https://tikwm.com/api/?url=${url}`);
    const data = await response.json();

    res.json({
      success: true,
      video: data.data.play
    });

  } catch (err) {
    res.json({ success: false });
  }
});

app.listen(10000, () => console.log("API شغال 🔥"));
