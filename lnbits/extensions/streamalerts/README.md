<h1>Stream Alerts</h1>
<h2>Integrate Bitcoin Donations into your livestream alerts</h2>
The StreamAlerts extension allows you to integrate Bitcoin Lightning (and on-chain) paymnents in to your existing Streamlabs alerts!

![image](https://user-images.githubusercontent.com/28876473/127759038-aceb2503-6cff-4061-8b81-c769438ebcaa.png)

<h2>How to set it up</h2>

At the moment, the only service that has an open API to work with is Streamlabs, so this setup requires linking your Twitch/YouTube/Facebook account to Streamlabs.

1. Log into [Streamlabs](https://streamlabs.com/login?r=https://streamlabs.com/dashboard).
1. Navigate to the API settings page to register an App:  
![image](https://user-images.githubusercontent.com/28876473/127759145-710d53b6-3c19-4815-812a-9a6279d1b8bb.png)  
![image](https://user-images.githubusercontent.com/28876473/127759182-da8a27cb-bb59-48fa-868e-c8892080ae98.png)  
![image](https://user-images.githubusercontent.com/28876473/127759201-7c28e9f1-6286-42be-a38e-1c377a86976b.png)  
1. Fill out the form with anything it will accept as valid. Most fields can be gibberish, as the application is not supposed to ever move past the "testing" stage and is for your personal use only.
In the "Whitelist Users" field, input the username of a Twitch account you control. While this feature is *technically* limited to Twitch, you can use the alerts overlay for donations on YouTube and Facebook as well.
For now, simply set the "Redirect URI" to `http://localhost`, you will change this soon.
Then, hit create:  
![image](https://user-images.githubusercontent.com/28876473/127759264-ae91539a-5694-4096-a478-80eb02b7b594.png)  
1. In LNbits, enable the Stream Alerts extension and optionally the SatsPayServer (to observe donations directly) and Watch Only (to accept on-chain donations) extenions:  
![image](https://user-images.githubusercontent.com/28876473/127759486-0e3420c2-c498-4bf9-932e-0abfa17bd478.png)  
1. Create a "NEW SERVICE" using the button. Fill in all the information (you get your Client ID and Secret from the Streamlabs App page):  
![image](https://user-images.githubusercontent.com/28876473/127759512-8e8b4e90-2a64-422a-bf0a-5508d0630bed.png)  
![image](https://user-images.githubusercontent.com/28876473/127759526-7f2a4980-39ea-4e58-8af0-c9fb381e5524.png)  
1. Right-click and copy the "Redirect URI for Streamlabs" link (you might have to refresh the page for the text to turn into a link) and input it into the "Redirect URI" field for your Streamelements App, and hit "Save Settings":  
![image](https://user-images.githubusercontent.com/28876473/127759570-52d34c07-6857-467b-bcb3-54e10679aedb.png)  
![image](https://user-images.githubusercontent.com/28876473/127759604-b3c8270b-bd02-44df-a525-9d85af337d14.png)  
1. You can now authenticate your app on LNbits by clicking on this button and following the instructions. Make sure to log in with the Twitch account you entered in the "Whitelist Users" field:  
![image](https://user-images.githubusercontent.com/28876473/127759642-a3787a6a-3cab-4c44-a2d4-ab45fbbe3fab.png)  
![image](https://user-images.githubusercontent.com/28876473/127759681-7289e7f6-0ff1-4988-944f-484040f6b9c7.png)  
If everything worked correctly, you should now be redirected back to LNbits. When scrolling all the way right, you should now see that the service has been authenticated:  
![image](https://user-images.githubusercontent.com/28876473/127759715-7e839261-d505-4e07-a0e4-f347f114149f.png)  
You can now share the link to your donations page, which you can get here:  
![image](https://user-images.githubusercontent.com/28876473/127759730-8dd11e61-0186-4935-b1ed-b66d35b05043.png)  
![image](https://user-images.githubusercontent.com/28876473/127759747-67d3033f-6ef1-4033-b9b1-51b87189ff8b.png)  
Of course, this has to be available publicly on the internet (or, depending on your viewers' technical ability, over Tor).
When your viewers donate to you, these donations will now show up in your Streamlabs donation feed, as well as your alerts overlay (if it is configured to include donations).
<h3>CONGRATS! Let the sats flow!</h3>
