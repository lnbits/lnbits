// FIXME(nochiel) If the host leaves then rejoins the conference, he has to reprocess all the events all over again.
// - Save a conference timestamp and don't process messages before that timestamp.
// TODO(nochiel) Handle errors from LNBits.api calls. 
// - Which errors should the host user see?
// TODO(nochiel) Ref. Use UserManager extension?
// See https://github.com/LightningTipBot for how to use the UserManager API .
// TODO(nochiel) Wrap jitsi in  a vue component
/*
 * TODO(nochiel) For each participant, add a 'pay Lightning' component.
 *   - Generates an invoice without an amount.
 *   - Show a QR code.
 *   - Allow the user to copy the bolt11 string.
*/

// TODO(nochiel) Chat bot
// When a participant joins a conference, the participant is not running LNBits.
// Therefore, we have 2 options for implementation:
// 1. Custom UX (we'll do this eventually)
//      - Use LibJitsiMeet to create an LNBits extension that only uses jitsi in the backend.
//      - With a custom UX, we can ensure that participants always see our LNBits-Jitsi app and the features we want.
//      - Maximum flexibility.
// 2. Chat commands (simple, easy to prototype)
//      - Use lntxbot/LightningTipBot command UX.
//      - All we have to do is handle commands.
//      - /pay participant_id [amount]
//              - participant is given a blank/filled invoice that they can pay to using an external wallet.
//      - /wallet pay participant_id amount
//              - participant pays participant_id using the balance in their LNBits wallet.
//


// ref. https://github.com/jitsi/jitsi-meet/blob/master/modules/API/external/external_api.js
// import "./external_api.js";
// import "lib-jitsi-meet.min.js";
// import "./jitsi_external_api.js";

const assert = console.assert;

function log(message, ...rest) {
    console.log(`%c ${message}`,  'background: steelblue; color: white; font-size:14px', ...rest);
}


function notImplemented() {
    assert(false, 'not implemented');
}

function jitsiFunctions(api) {

    return {


        onConnectionEstablished: function(data) {

            const options = {
                roomName: roomName,
                parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
                // height: '700px',         // FIXME(nochiel) Make this 75% of the viewport.
                // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
                // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
                // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
            }

        },

        hello: function(name) {
            log(`hello ${name}`);
        },

    }
}

const app = new Vue({
    el: '#vue',
    mixins: [windowMixin],

    data: function() {
        return {  api: null, conference: '',
        }; 
    },

    /*
    computed: {

        api() {

            let domain = 'meet.jit.si';
            let tenant = 'AAAA';
            let roomName = 'room_AAAA';

            const options = {
                roomName: roomName,
                parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
    // height: '500px',         // FIXME(nochiel) Make this 75% of the viewport.
    // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
    // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
    // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
            };

            let api = new JitsiMeetExternalAPI(domain, options);
            return api;  
        },

    },
    */

    mounted: function () {

        // TODO(nochiel) Show user dialog so they can set these when creating a conference?
        let domain = 'meet.jit.si';
        let tenant = 'AAAA';
        let roomName = 'room_AAAA';

        const options = {
            roomName: roomName,
            parentNode: document.querySelector('#meet'),    // TODO(nochiel) Create this node in index.html.
            height: '700px',         // FIXME(nochiel) Make this 75% of the viewport.
            // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere des nothing.
            // configOverwrite : {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js
            // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
        };

        this.api = new JitsiMeetExternalAPI(domain, options);
        assert(this.api != null);
        log('this: ', this);
        jitsiFunctions = jitsiFunctions.bind(this);
        jitsiFunctions  = jitsiFunctions(this.api);
        const api = this.api;
        // console.log('jitsi event names:', api.events);

        // FIXME(nochiel) Does nothing. My assumption is that the api is destroyed even though I made it global.
        // FINDOUT How do I do handle events in Vue? Specifically, how do I determine why this listeners aren't running?
        api.on('videoConferenceJoined', this.videoConferenceJoined);
        api.on('participantJoined', this.newParticipant);
        api.on('incomingMessage', this.incomingMessage);

        // FIXME(nochiel) Why don't these work? 
        api.on('errorOccurred', function (data) { console.error('error in Jitsi'); });
        api.on('log', (data) => { log('logging'); });     

    },

    methods: {

        async test() {
            // TODO(nochiel) Tests for all api flows.
            //
        },

        async getWallet(walletId) {

            let result = await LNbits.api
                .request(
                    'GET',
                    `/jitsi/api/v1/conference/participant/wallet/${walletId}`,
                    this.g.user.wallets[0].inkey,
                );

            return result;
        },

        mSatstoSats(v) {
            let result = 0
            if(v > 0) {
                result = v / 1000;
            }
            return result;
        },

        async incomingMessage(event) {
            /*
                {
                    from: string, // The id of the user that sent the message
                    nick: string, // the nickname of the user that sent the message
                    privateMessage: boolean, // whether this is a private or group message
                    message: string // the text of the message
                }
            */
            if(!this._isMounted) return;

            log(`incomingMessage: from "${event.from}". Says: ${event.message}`);

            if(event.message.startsWith('/')) {
                // TODO(nochiel) Chat commands shouldn't show up in group chat. How do we filter out commands?
                // - We won't. Instead, the bot will reply privately to the user who is commanding it.
                this.getParticipant(this.conference, event.from)
                    .then(participant => {

                        assert(participant, `Jitsi participant ${event.from} does not exist in the LNBits database.`);
                        this.getWallet(participant.wallet)
                            .then(wallet => {

                                assert(wallet != null, `Jitsi participant ${event.from} does not have a wallet in the database.`);
                                let words = event.message.substring(1,).split(' ');
                                let command = words[0];
                                switch (command) {
                                    case 'balance': {
                                        log(`incomingMessage: command balance`);
                                        log(`incomingMessage: ${event.from} has a balance of: ${wallet.balance}`);
                                        // FIXME(nochiel) Make this a private message
                                        this.api.executeCommand('sendChatMessage',
                                            `Your balance is ${this.mSatstoSats(wallet.balance_msat)}`,
                                            event.from, // the receiving participant ID or empty string/undefined for group chat.
                                        );

                                    }; break;

                                    case 'pay': {
                                        log(`incomingMessage: command pay`);

                                        let payeeName = event.message.substring('/pay'.length - 1).trim();
                                        if(payeeName == '') {

                                            log('incomingMessage: command was "/pay" but no payee name was given');
                                            // TODO(nochiel) Tell the user the syntax to use and give an example of how to pay the host.


                                        }
                                    }; break;
                                }
                            });
                    });
            }
        },

        async videoConferenceJoined(event) {
            /*
                {
                    roomName: string, // the room name of the conference
                    id: string, // the id of the local participant
                    displayName: string, // the display name of the local participant
                    avatarURL: string // the avatar URL of the local participant
                }
                */

            if(!this._isMounted) return;
            assert(event.roomName != null);

            this.conference = event.roomName;
            data = {
                conference: event.roomName,     
                admin: event.id,
            };
            LNbits.api
                .request(
                    'POST',
                    '/jitsi/api/v1/conference',
                    this.g.user.wallets[0].inkey,
                    data
                )
                .then( response => {
                    log('videoConferenceJoined: response from creating conference: ', response.data);
                });

        },


        async getConference(adminId) {

            // FIXME(nochiel) Handle errors.
            assert(adminId != null);
            let result = null;
            response = await LNbits.api
                .request(
                    'GET',
                    `/jitsi/api/v1/conference/${adminId}`,
                    this.g.user.wallets[0].inkey,
                )

            if(response != null) {
                result = response.data;
            }

            return result;

        },

        async getParticipant(conference, participant) {
            assert(conference && conference != '', 'conference id must be given');
            assert(participant && participant != '', 'participant id must be given');
            log('getParticipant');

            let result = null;
            try {
                let response = await LNbits.api
                    .request(
                        'GET',
                        `/jitsi/api/v1/conference/${conference}/participant/${participant}`,
                        this.g.user.wallets[0].inkey,
                    );
                result = response.data;
            } catch(e) {
                log('getParticipant: error: ', e);
            }
            return result;
        },


        async newParticipant(event) {

            /*
                {
                    id: string, // the id of the participant
                    displayName: string // the display name of the participant
                }
            */

            if(!this._isMounted) return;
            assert(event.id != '');
            log('newParticipant: ', event.id);

            // Give new participants an LNBits account.
            // FINDOUT Should I create a new admin wallet for each conference and save the conference with the wallet?
            if(this.conference != '') {
                log(`newParticipant: creating ${event.id} in conference ${this.conference}`);

                // TODO(nochiel) FINDOUT How do I create a new LNBits wallet? 
                // The LNBits api changes the window location when a new wallet is created. 
                var data = { participant: event.id, conference: this.conference };

                let participant = await this.getParticipant(data.conference, data.participant);
                log('newParticipant: got participant: ', participant);
                if(!participant) {

                    // FINDOUT(nochiel) What do we need to store with the participant so that we can generate invoices?
                    // - create a new LNBits userId.
                    // - let walletName = participant.id
                    // FINDOUT(nochiel) How is a user wallet identified?

                    LNbits.api
                        .request(
                            'POST',
                            '/jitsi/api/v1/conference/participant',
                            this.g.user.wallets[0].inkey,
                            data
                        ).then(response => {
                            log('newParticipant: result: ', response.data);
                        });

                }

            }



        },

}

});

