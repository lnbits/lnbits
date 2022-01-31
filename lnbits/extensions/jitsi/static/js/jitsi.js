// TODO(nochiel) Handle errors from LNBits.api calls. 
// - Which errors should the host user see?

// FIXME(nochiel) Cleanup: Use consistent language for:
// - Jitsi meeting.
// - Jitsi host.

// ref. https://github.com/jitsi/jitsi-meet/blob/master/modules/API/external/external_api.js

const assert = console.assert;
/*
function assert(condition, message, ...args) {
    // assert with an exception
    console.assert(condition, message, ...args);
    throw new Error(message);
}
*/

function logError(message, ...rest) {
    console.error(`error: %c ${message}`,  'background: coral; color: white; font-size:14px', ...rest);
}

function error(message, ...rest) {
    logError(message, ...rest);
    // TODO(nochiel) Show the user an error notification.
}

function log(message, ...rest) {
    console.log(`%c ${message}`,  'background: steelblue; color: white; font-size:14px', ...rest);
}


function NOTIMPLEMENTED() {
    throw new Error('NOT IMPLEMENTED');
}

const app = new Vue({

    el: '#vue',
    mixins: [windowMixin],

    data: function() {

        return {  
            api         : null,
            conference  : null,     // The jitsi id of the current conference.
            wallet      : null,

            setupDialog : {
                show            : true,
                data            : {
                },
            },

            jitsiPanel  : {
                show : false,
                data : {},    
            }
        }; 

    },

    methods: {

        setupJitsi () {

            let domain = 'meet.jit.si';

            // let random = Math.floor(Math.random() * 0xFFFFFFFF);    // Use this to generate insecure unique ids. 
            // 'tenant' is only relevant if the user is running their own Jitsi server. 
            // We would want to use the 'tenant' option to allow the LNBits user to run multiple conferences simultaneously. 
            // Ref. https://digitalguardian.com/blog/saas-single-tenant-vs-multi-tenant-whats-difference
            // let tenant = `tenant_${random}`;  

            const options = {
                roomName: this.setupDialog.data.roomName ?? `LNBits-${random}`,     // FIXME(nochiel) Generate a unique default room name. 
                parentNode: document.querySelector('#meet'),   // ref. templates/jitsi/index.html 
                height: '700px',         // FIXME(nochiel) Make this 75% of the viewport.
                // chromeExtensionBanner: {},       // FIXME(nochiel) Does nothing.
                configOverwrite : { 
                // apiLogLevels: ['warn', 'log', 'error', 'info', 'debug'],     // see: https://github.com/jitsi/jitsi-meet/blob/master/config.js 
                },    
                // onload : jitsiOnload,       // FIXME(nochiel) Goes nowhere does nothing.
                // interfaceConfigOverwrite: {};    // see: https://github.com/jitsi/jitsi-meet/blob/master/interface_config.js
            };

            log('jitsi options: ', options);

            // TODO(nochiel) Use this.g.user to set the administrator participant's details.
            log('LnBits user: ', this.g.user);

            this.api = new JitsiMeetExternalAPI(domain, options);
            this.jitsiPanel.show = true;
            assert(this.api);
            // log('this: ', this);
            const api = this.api;

            // console.log('jitsi event names:', api.events);
            api.on('videoConferenceJoined', this.videoConferenceJoined);
            api.on('participantJoined', this.newParticipant);
            api.on('incomingMessage', this.incomingMessage);
            // api.on('chatUpdated', this.chatUpdated);        

            // FIXME(nochiel) Why don't these work? 
            // api.on('errorOccurred', function (data) { console.error('error in Jitsi'); });
            api.on('log', event  => { log(`logging[${event.logLevel}`, ...event.args); });     

        },

        sendSetupFormData() {

            this.setupDialog.show = false;
            this.setupJitsi();
        },


        async test() {
            // TODO(nochiel) Tests for all api flows.
            
            NOTIMPLEMENTED();

        },

        async chatUpdated(event) {
            /*
                {
                    'unreadCount': unreadCounter, // the unread message(s) counter,
                    'isOpen': isOpen, // whether the chat panel is open or not
                }
            */

            log('chatUpdated: event: ', event);
        },

        async getWallet(conferenceId, participantId) {
            assert(conferenceId);
            assert(participantId);

            let result;

            data = {
                conferenceId: conferenceId,
                participantId: participantId
            }

            if(conferenceId && participantId) {
                result = LNbits.api
                    .request(
                        'GET',
                        // `/jitsi/api/v1/wallet`,
                        `/jitsi/api/v1/conference/${conferenceId}/participant/${participantId}/wallet`,
                        this.wallet.adminkey,
                        /*
                        null,
                        data,
                        */

                    )
                    .then(response => {

                        if(response.data) {

                            log('getWallet: response: ', response);
                            let wallet = LNbits.map.wallet(response.data);
                            assert(wallet.id, wallet);

                            return  wallet;
                        }

                    });
            }

            return result;
        },

        async incomingMessage(event) {

            if(!this._isMounted) return;
            if(!this.conference) return;
            log('incomingMessage: event: ', event);
            /*
                {
                    from: string, // The id of the user that sent the message
                    nick: string, // the nickname of the user that sent the message
                    privateMessage: boolean, // whether this is a private or group message
                    message: string // the text of the message
                }
                */

            // FIXME(nochiel) The bot is run as the host. Ideally, the bot should be an independent participant.
            // FIXME(nochiel) If the host (local user) leaves the chat, we have no way of knowing infallibly
            // which commands have already been processed. Therefore, we should log messages and send a sentinel 
            // message into group chat. The sentinel contains a timestsamp of the last processed message.
            // When the host joins the conference, check the log for the number of messages saved. 
            // Start processing messages after the n + 1 message.


            /*
                getParticipantsInfo returns {displayName: 'b', formattedDisplayName: 'b', avatarURL: undefined, participantId: '259448ce'}
                */
            const participants = this.api.getParticipantsInfo();

            const sendChatMessage = (to, message) => {

                const recipient = participants.find(p => p.participantId == to)
                    ?.displayName;
                assert(to && recipient, `participant id ${to} is not in this conference`);

                if((to && recipient) || !to) {
                    this.api.executeCommand('sendChatMessage',
                        message,
                        to, // the receiving participant ID or empty string/undefined for group chat.
                    );
                }

            };

            const logChatMessage = async (event) => {
                // FIXME(nochiel) If the host leaves then rejoins the conference, he has to reprocess all the events all over again because he is sent the whole chatlog. 
                // - Save a conference timestamp and don't process messages before that timestamp.
                // - How do we filter out old messages without accidentally ignoring old messages?
                // - The host can send themselves a private timestamp every time he receives a message. 
                // - Or: create a participant who is the chatbot. The host can then send logs to the chatbot.
                // FIXME(nochiel) Upstream: events should have a timestamp. We need to know when a chat message was sent.

                // log('logChatMessage: event: ', event);
                assert(event);
                assert(event.message);

                let data = event;
                data.timestamp = performance.now();
                /*
                    let result = await LNbits.api
                    .request(
                        'POST',
                        '/jitsi/api/v1/conference/${this.conference}/message',
                        this.g.user.wallets[0].inkey,       // FIXME(nochiel) Make sure we use the correct API key for the hosts wallet. Do we know that the first wallet is the correct one?
                        data,
                    );
                    */
                let result = data;
                log('logChatMessage: ', result);
                return result;

            };

            const message = await logChatMessage(event);
            if(message) {

                log(`incomingMessage: from: "${message.from}"\nmessage: "${message.message}"\nat: ${message.timestamp}`);

                if(message.message.trim().startsWith('/')) {

                    // TODO(nochiel) Chat commands shouldn't show up in group chat. How do we filter out commands?
                    // - We can't with this Jitsi api. Instead, the bot will reply privately to the user who is commanding it.
                    // - When we switch to a custom UI, we'll be able to control chat better if we need to.
                    this.getParticipant(this.conference, message.from)
                        .then(participant => {

                            assert(participant, `Jitsi participant ${message.from} does not exist in the LNBits database.`);
                            this.getWallet(this.conference, participant.id)
                                .then(async wallet => {

                                    log(`incomingMessage: using ${message.from}'s wallet: `, wallet);
                                    assert(wallet, `Jitsi participant ${message.from} does not have a wallet in the database.`);

                                    const getInvoice = async (payee, amount, memo) => {

                                        const payeeName = participants.find(p => p.participantId == payee)
                                            ?.displayName;

                                        memo ??= `Paying ${payeeName} in the "${this.conference}" Jitsi meeting.`;

                                        log(`incomingMessage.getInvoice: pay ${payeeName}(${payee}), ${amount}, ${memo}`);

                                        return this.getParticipant(this.conference, payee)
                                            .then(async participant => {

                                                assert(participant);
                                                let wallet = await this.getWallet(this.conference, participant.id);
                                                assert(wallet);
                                                log('incomingMessage.getInvoice: payee: ', participant.user , ' wallet: ', wallet);

                                                return LNbits.api.createInvoice(wallet, amount, memo)
                                                    .then(response => response.data)
                                                    .then(data => {

                                                        assert(data);
                                                        log('incomingMessage.getInvoice: createInvoice response.data: ', data);
                                                        assert(data.payment_request);  

                                                        let result = { 
                                                            paymentRequest: data.payment_request, 
                                                            qrCode: null,       // TODO(nochiel)
                                                        };

                                                        return result;
                                                    });
                                            });
                                    };


                                    let words = message.message.substring(1,).match(/\w+/g);
                                    if(words) {

                                        const HELPDEPOSIT = 'You can deposit sats into your wallet for this chat sing the "/deposit" command to get a Lightning invoice.',
                                            HELPDEPOSITSYNTAX = `/deposit 💰 Deposit funds into your wallet for the ${this.conference} conference call: /deposit <amount> [<memo>]`,
                                            HELPBALANCE = 'Use the "/balance" command to check your balance.',
                                            HELPPAYSYNTAX = '/pay 💸 Send funds to a user: /pay <amount> <user or id> [<memo>]';

                                        let command = words[0];
                                        switch (command) {


                                            case 'help': { 

                                                sendChatMessage(message.from,
                                                    'To run a command, send a chat message starting with a "/" followed by the command name:' + '\n\n' +
                                                    '/balance ⚖️ Check your balance: /balance' + '\n\n' +
                                                    HELPPAYSYNTAX + '\n\n' +
                                                    HELPDEPOSITSYNTAX + '\n\n' +
                                                    '/users 😀 List user names and ids of participants in this meeting.' + '\n\n' +
                                                    '/help 📖 Read this help.' + '\n\n' +
                                                    '/donate ❤️ Donate to the project: /donate <amount>'
                                                );

                                            }; break;

                                            case 'users': {

                                                NOTIMPLEMENTED();       // TODO(nochiel)

                                            }

                                            case 'donate': {

                                                // TODO(nochiel) Show how to donate to LNbits.
                                                // TODO(nochiel) Show how to donate to @nochiel or whomever is working on the Jitsi extension.
                                                log('incomingMessage: donate: ');
                                                NOTIMPLEMENTED();       

                                            }; break;

                                            case 'balance': {
                                                log(`incomingMessage: command 'balance'`);

                                                log(`incomingMessage: ${message.from} has a balance of: ${wallet.fsat} sats.`);
                                                sendChatMessage(message.from,
                                                    `Your Lightning wallet balance for this conference is ${wallet.fsat} satoshis` + '\n' +
                                                    `You can manage your LNbits wallet by visiting: ${window.location.origin + wallet.url} (YOU SHOULD SAVE THIS URL!)`);


                                            }; break;

                                            case 'deposit': {
                                                // TODO(nochiel) When the deposit invoice is paid, tell the participant that the deposit has succeeded.

                                                if(words.length < 2) {
                                                    sendChatMessage(message.from, HELPDEPOSIT + '\n\n' + HELPDEPOSITSYNTAX);
                                                    return;
                                                }

                                                let amount = Number(words[1])
                                                if(isNaN(amount) || amount <= 0) { 
                                                    sendChatMessage(message.from, `The amount you entered is "${words[1]}" but it is not a valid amount!`);
                                                    sendChatMessage(message.from, HELPDEPOSITSYNTAX);
                                                    return; 
                                                }

                                                let name = participants.find(p => p.participantId == message.from) 
                                                ?.displayName;
                                                let memo = `Deposit for "${name}" in the "${this.conference}" Jitsi conference call.`;
                                                if(2 in words) { memo = words.slice(2).join(' ') }

                                                getInvoice(message.from, amount, memo)
                                                .then(invoice => {
                                                    assert(invoice, 'An invoice was not created');
                                                    sendChatMessage(message.from, `Use your Lightning wallet to deposit into your LNbits wallet with the following invoice:\n\n`
                                                        + `${invoice.paymentRequest}`);
                                                })
                                                .catch(e => {

                                                    logError('incomingMessage: ', e);
                                                    sendChatMessage(message.from, 'LNbits failed to generate an invoice for your deposit. Please try again or inform the host of this conference call that wallets are not working.');
                                                });

                                            }; break;

                                            case 'pay': {

                                                log(`incomingMessage: command pay`);
                                                const HELPSYNTAXMESSAGE = `Please use the correct syntax for this command.\n\n${HELPPAYSYNTAX}`;

                                                assert(participant, 'no participant has been set');
                                                const payer = participant;

                                                if(words.length < 3) {
                                                    sendChatMessage(payer.id, HELPSYNTAXMESSAGE);
                                                    return;
                                                }

                                                let amount = 0;
                                                amount = Number(words[1]);
                                                if(isNaN(amount) || amount <= 0) { 
                                                    sendChatMessage(payer.id, `The amount you entered is "${words[1]}" but it is not a valid amount!`);
                                                    sendChatMessage(payer.id, HELPSYNTAXMESSAGE);
                                                    return; 
                                                }

                                                const payerName = participants.find(p => p.participantId == payer.id)
                                                ?.displayName;

                                                const payeeName = words[2];
                                                log(`incomingMessage: payee: ${payeeName}`);
                                                const payee = participants.find(p => p.displayName == payeeName)
                                                ?.participantId;
                                                if(!payee) {
                                                    sendChatMessage(payer.id, `You tried to send money to ${payeeName} but they aren't in this meeting! Please try again with a name that is in use by someone here. Use the '/users' command to get a list of users and their ids then try paying to the id if the username doesn't work.`);
                                                    return;
                                                }

                                                let memo;
                                                if (3 in words) { memo = words.slice(3).join(' '); }

                                                const pay = async (payer, wallet, amount, payeeId, memo) => 

                                                    getInvoice(payeeId, amount, memo)
                                                        .then(invoice => {

                                                            // assert(participant.id == payer, `using payer participant: ${participant}`);
                                                            // assert(wallet.user == participant.user, `using payer wallet: ${wallet}`);

                                                            if(wallet.sat < amount) {


                                                                sendChatMessage(payer.id, 
                                                                    `You don't have enough sats to send that amount from your LNbits wallet. Your balance is ${wallet.sat}.`);
                                                                sendChatMessage(payer.id, HELPBALANCE);
                                                                sendChatMessage(payer.id, HELPDEPOSIT);


                                                                // sendChatMessage(payer.id, `Paying ${payeeName} ${amount} sats.`);
                                                                sendChatMessage(payer.id,
                                                                    `Use your Lightning wallet to pay ${payeeName} with the following invoice:\n\n` +
                                                                    `${invoice.paymentRequest}`);

                                                                return;
                                                            }

                                                            return LNbits.api.payInvoice(wallet, invoice.paymentRequest)
                                                                .then(response =>  response.data)
                                                                .then(({payment_hash, }) => payment_hash);
                                                        })
                                                        .catch(e => {
                                                            logError('incomingMessage: ', e);
                                                            sendChatMessage(payer.id, 'Payment failed. Please try again or inform the host of this conference call that payments are not working.');
                                                        });


                                                pay(participant, wallet, amount, payee, memo)
                                                    .then(payment_hash => {

                                                        if(payment_hash) {
                                                            log(`incomingMessage.pay: Payment(${payment_hash}) from ${participant.id} to ${payee} for ${amount} sats.`);
                                                            sendChatMessage(payee, `${payerName} has paid you ${amount} sats.`);        
                                                            sendChatMessage(participant.id, `You have paid ${payeeName} ${amount} sats.`);        
                                                        }
                                                    })
                                                    .catch(e => {
                                                        // TODO(nochiel) Give specific error messages to the payer.
                                                        // - Insufficient balance error.
                                                        // - Server/Node error
                                                        log('pay: ', e);
                                                        sendChatMessage(participant.id, `Sorry, your payment of ${amount} to ${payeeName} failed! Please try again.`);
                                                    });

                                                return;

                                                }; break;

                                            }
                                    }
                            });
                        });
                    }
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

            // The host can exit and rejoin the conference mmultiple times.
            // - Rejoining creates a new jitsi participant id. 
            //          
            //          - If we create a new wallet, is there a way to make sure that the LNBits user has access to all their wallets? Ans. Yes, just make sure that we create a new wallet for the lnbits user. i.e. don't create a new user.

            if(!this._isMounted) return;
            log('videoConferenceJoined: ', event);
            assert(event.roomName);     
            this.conference = event.roomName;
            this.wallet = this.g.user.wallets[0];

            data = {
                conferenceId: event.roomName,     
                admin: event.id,
            };
            LNbits.api
                .request(
                    'POST',
                    '/jitsi/api/v1/conference',
                    this.wallet.adminkey,
                    data
                )
                .then(response => {

                    log('videoConferenceJoined: response : ', response.data);
                    let conference = response.data;
                    if(conference.name) {
                        assert(conference.name,
                            `the conference in the response is invalid. conference.name: "${conference.name}"`); 
                        this.getParticipant(conference.name, event.id)
                            .then(async admin => {

                                assert(admin.id == event.id);

                                // FIXME(nochiel) If the admin participant is newly created,
                                // this.g.user.wallets should be refreshed to get the new wallet.
                                // assert this.g.user.wallets.find(w => w.id == admin.wallet);
                                // TODO(nochiel) FINDOUT Can we use: LNbits.api.getWallet(admin.wallet) ?
                                log('videoConferenceJoined: admin: ', admin);
                                this.wallet = await this.getWallet(this.conference, admin.id).then(wallet => this.wallet = wallet);
                                log('created admin who will use wallet: ', this.wallet);

                            });
                    }

                })
                .catch(e => {
                    logError('videoConferenceJoined: error : ', e.detail);
                    this.conference = '';
                    // TODO(nochiel) Show the admin an error and ask them to try to create the conference again.
                });
        },

        async getConference(adminId) {

            // FIXME(nochiel) Handle errors.
                assert(adminId);
            let result = null;
            result = LNbits.api
                .request(
                    'GET',
                    `/jitsi/api/v1/conference/${adminId}`,
                    this.wallet.adminkey,
                )
                .then(response => response.data);

            return result;

        },

        async getParticipant(conference, participant) {
            /*
                returns: { 
                    id: str
                    conference: str
                    user: str
                    wallet: str
                }
                */
            assert(conference, 'conference id must be given');
            assert(participant, 'participant id must be given');

            let result = null;
            if(conference && participant) {

                log(`getParticipant: ${participant}`);

                result = LNbits.api
                    .request(
                        'GET',
                        `/jitsi/api/v1/conference/${conference}/participant/${participant}`,
                        this.wallet.adminkey,
                    )
                    .then(response => {
                        let result = response.data;
                        log('getParticipant: data: ', result);
                        return result;
                    })
                    .catch(e => {
                        log('getParticipant: error: ', e);
                    });
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

            // FIXME(nochiel) Unique nicknames: Prevent participants from having the same displayName. 
            // - When a new participant joins, if they choose a nick that is already in use,
            // append an ordinal to the name.
            // - If the participant does not have a nick, give them a standard name with an ordinal. 
            // The Jitsi api doesn't allow us to rename participants so we can't actually fix this problem.

            assert(event.id);
            log('newParticipant: id: ', event.id);

            // Give new participants an LNBits account.
            assert(this.conference, 'The conference has not been set! We cannot create participants unless we have a conference. ');
            if(this.conference) {
                log(`newParticipant: creating ${event.id} in conference ${this.conference}`);

                let participant = await this.getParticipant(this.conference, event.id);
                log('newParticipant: got participant: ', participant);
                if(!participant) {

                    let data = { id: event.id };
                    LNbits.api
                        .request(
                            'POST',
                            `/jitsi/api/v1/conference/${this.conference}/participant`,
                            this.wallet.adminkey,
                            data
                        )
                        .then(response => {
                            log('newParticipant: result: ', response.data);
                        })
                        .catch(e => {
                            // TODO(nochiel) Show the admin an error.
                            logError('newParticipant: error when creating new participant', e );
                        });

                }

            }



        },

    }

});

