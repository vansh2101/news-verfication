// Test script for SerpAPI integration
const { getJson } = require("serpapi");

// Use the API key from your code
const apiKey = "79aa6b8adbffdbb4ad7d685307f9befbc23734b41ef7587b2c67173d5b056256";

console.log("Testing SerpAPI integration...");

getJson({
  api_key: apiKey,
  engine: "google_news",
  hl: "en",
  gl: "us",
  num: 5
}, (json) => {
  console.log("Full SerpAPI Response:");
  console.log(JSON.stringify(json, null, 2));
  
  if (json.error) {
    console.error("Error:", json.error);
  } else if (json.news_results) {
    console.log(`\nFound ${json.news_results.length} news articles:`);
    json.news_results.slice(0, 3).forEach((article, i) => {
      console.log(`\n${i + 1}. ${JSON.stringify(article, null, 2)}`);
    });
  } else {
    console.log("No news_results field found in response");
  }
});
