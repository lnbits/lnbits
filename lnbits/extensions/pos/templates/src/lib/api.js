export const createInvoice = async (value, memo = 'lnbitsPoS') => {
    try {
        const resp = await fetch('/api/v1/invoices',{
            method: 'POST',
            headers: {"Grpc-Metadata-macaroon": "xxxxxxx"},
            body: JSON.stringify({value, memo})
        })
        const invoice = await resp.json()
        return invoice.pay_req
    } catch (error) {
        throw new Error(error)
    }
}

export const checkInvoice = async (paymentHash) => {
    try {
        const resp = await fetch(`/api/v1/invoices/${paymentHash}`,{
            method: 'GET',
            headers: {"Grpc-Metadata-macaroon": "xxxxxxx"}
        })
        const invoice = await resp.json()
        return invoice.PAID === 'TRUE'
    } catch (error) {
        throw new Error(error)
    }
}