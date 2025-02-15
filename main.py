import os
import sys
import datetime
import feedparser
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

endpoint = "https://models.inference.ai.azure.com"
model_name = os.environ["MODEL_NAME"]
token = os.environ["SECRET_GITHUB_TOKEN"]
feeds_file = os.environ["FEEDS_FILE"]
keywords = os.environ["KEYWORDS"]
strongKeywords = os.environ["STRONG_KEYWORDS"]
systemMessageStart = os.environ["SYSTEM_MESSAGE_START"]
systemMessage = f"{systemMessageStart} Here are some of the keywords I am generally interested in {keywords}. Here are some keywords I am strongly interested in {strongKeywords}, and you should recommend these as much as possible."

class RecommendationItem:
    promptMessage = "Here is an RSS feed item and you have to decide whether to recommend this to me. \nTitle: {}\nContent: {}\n\nPlease respond a rating on the scale from 0 to 10 where 10 is highly recommended and 0 is least recommended. Put the rating number at the start of response. Also include reason in less than 100 words without any newline character."
    
    def __init__(self, rawEntry):
        self.title = rawEntry.title
        self.summary = rawEntry.summary
        self.link = rawEntry.link
        self.rating = -1
        self.reason = "N/A"
        
    def getRecommendationPrompt(self):
        return self.promptMessage.format(self.title, self.summary)
    
    def toHTML(self) -> str:
        # Put rating and title together as a header with link
        # then put recommendation reason
        return f"<h2><a href=\"{self.link}\">{self.rating} - {self.title}</a></h2><p>{self.reason}</p>"
    
    def toStr(self) -> str:
        return self.__str__()
    
    def __str__(self) -> str:
        res  = "--------------------------------------------\n"
        res += f"{self.rating} - {self.title}\n"
        res += f"{self.link}\n"
        res += f"{self.reason}\n"
        res += "\n--------------------------------------------\n"
        return res

def get_recommendation(client: ChatCompletionsClient, systemMessage: str, promptMessage: str) -> str:
    response = client.complete(
        messages=[
            SystemMessage(content=systemMessage),
            UserMessage(content=promptMessage),
        ],
        temperature=1.0,
        top_p=1.0,
        max_tokens=1000,
        model=model_name
    )
    return response.choices[0].message.content

# Create a client and parse the RSS feed
client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(token),
)

emailBody = ""
discardedItems = []
print(f"Started processing {feeds_file} at {datetime.datetime.now()}")
with open(feeds_file, "r") as f:
    for rssLink in f.readlines():
        rssLink = rssLink.strip()
        if rssLink.startswith("#"):
            continue
        print(f"Processing {rssLink}")
        feeds = feedparser.parse(rssLink)
        
        if not feeds.entries:
            print(f"Skipping {rssLink} as no entries found")
            continue
        
        # Feed title
        recommendedItems = []
        for entry in feeds.entries:
            item = RecommendationItem(entry)
            item.reason = get_recommendation(client, systemMessage, item.getRecommendationPrompt())
            try:
                item.rating = int(item.reason[:2])
            except ValueError:
                item.rating = -1
            
            # Filter out items with rating less than 5
            if item.rating >= 5:
                recommendedItems.append(item)
            else:
                discardedItems.append(item)
        
        # Construct email body
        if recommendedItems:
            emailBody += f"<h1><a href=\"{feeds.feed.link}\">{feeds.feed.title}</a></h1>"
            for item in recommendedItems:
                emailBody += item.toHTML()
        
if emailBody:
    print("Dumping the following email body to ./email.html")
    print(emailBody)
    with open('./email.html', 'w') as f:
        print(emailBody, file=f)

if discardedItems:
    print("Here are the discarded items:")
    for item in discardedItems:
        print(item.toStr())
        
print(f"Done processing {feeds_file} at {datetime.datetime.now()}")
