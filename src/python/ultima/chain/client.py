"""Blockchain interface client"""
import requests
import time

from typing import Any, Dict
from ultima.chain.account import Account, hex_leader
from ultima.chain.defs import (
    account_fields,
    api_url_types,
    e_msgs,
    msg_sig_start_byte as start_byte,
    rest_codes,
    rest_path_elems,
    rest_post_headers as h_fields,
    rest_response_fields,
    rest_urls,
    seps,
    tx_defaults,
    tx_fields,
    tx_sig_fields
)

class RestClient:
    """Interface to Aptos blockchain REST API

    Parameters
    ----------
    network : str
        As specified in :data:`~chain.defs.networks`

    Attributes
    ----------
    fullnode_url : str
        REST API url for fullnode interactions
    faucet_url : str
        REST API url for faucet

    Example
    -------
    >>> from ultima.chain.defs import networks
    >>> from ultima.chain.client import RestClient
    >>> client = RestClient(networks.devnet)
    >>> client.fullnode_url
    'https://fullnode.devnet.aptoslabs.com'
    >>> client.faucet_url
    'https://faucet.devnet.aptoslabs.com'
    """

    def __init__(
        self,
        network: str
    ) -> None:
        self.fullnode_url = rest_urls[network][api_url_types.fullnode]
        self.faucet_url = rest_urls[network][api_url_types.faucet]

    def construct_request_url(
        self,
        path_elems: list[str],
        query_pairs: dict[str, str] = None,
        faucet = False
    ) -> str:
        """Construct a REST request URL

        Parameters
        ----------
        path_elems : list of str
            Path elements to include in REST URL
        query_pairs : dict from str to str, optional
            Map from REST query string keys to values
        faucet : bool, optional
            Submit to faucet if True, otherwise to fullnode

        Returns
        -------
        str
            Constructed REST query URL

        Example
        -------
        >>> from ultima.chain.defs import networks
        >>> from ultima.chain.client import RestClient
        >>> client = RestClient(networks.devnet)
        >>> client.construct_request_url(
        ...     ['foo', 'bar'],
        ...     query_pairs={'do_it': 'yes', 'say_it': 'no'},
        ...     faucet=True
        ... )
        'https://faucet.devnet.aptoslabs.com/foo/bar?do_it=yes&say_it=no'
        """
        url = f'{self.fullnode_url}'
        if faucet:
            url = f'{self.faucet_url}'
        for elem in path_elems:
            url = url + seps.slash + elem
        if query_pairs is not None:
            url = url + seps.q_mark
            for key in query_pairs:
                if not url.endswith(seps.q_mark):
                    url = url + seps.amp
                url = url + key + seps.equal + query_pairs[key]
        return url

    def get_request_response(
        self,
        path_elems: list[str],
        query_pairs: dict[str, str] = None,
        faucet: bool = False,
    ) -> Dict[str, Any]:
        """Construct and submit REST request, returning response

        Parameters
        ----------
        path_elems : list of str
            Path elements to include in REST URL
        query_pairs : dict from str to str, optional
            Map from REST query string keys to values
        faucet : bool, optional
            Submit to faucet if True, otherwise to fullnode

        Returns
        -------
        requests.models.Response
            Response from the REST API
        """
        return requests.get(
            self.construct_request_url(path_elems, query_pairs, faucet)
        )

    def get_post_response(
        self,
        path_elems: list[str],
        query_pairs: dict[str, str] = None,
        faucet: bool = False,
        json: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Construct and submit REST post, returning response

        Parameters
        ----------
        path_elems : list of str
            Path elements to include in REST URL
        query_pairs : dict from str to str, optional
            Map from REST query string keys to values
        faucet : bool, optional
            Submit to faucet if True, otherwise to fullnode
        json : dict from str to Any, optional
            JSON data
        headers : dict from str to str, optional
            Header values

        Returns
        -------
        requests.models.Response
            Response from the REST API
        """
        return requests.post(
            self.construct_request_url(path_elems, query_pairs, faucet),
            json=json,
            headers=headers
        )

    def account(
        self,
        account_address: str
    ) -> Dict[str, str]:
        """Return account sequence number and authentication key

        Parameters
        ----------
        account_address : str
            Account address

        Returns
        -------
        dict from str to str
            Account info
        """
        response = self.get_request_response(
            [rest_path_elems.accounts, account_address]
        )
        assert response.status_code == rest_codes.success , response.text
        return response.json()

    def account_resources(
        self,
        account_address: str
    ) -> Dict[str, Any]:
        """Return all account resources

        Parameters
        ----------
        account_address : str
            Account address

        Returns
        -------
        dict from str to Any
            Account resources
        """
        response = self.get_request_response([
            rest_path_elems.accounts,
            account_address,
            rest_path_elems.resources
        ])
        assert response.status_code == rest_codes.success , response.text
        return response.json()

    def generate_tx(
        self,
        sender: str,
        payload: Dict[str, Any],
        max_gas_amount: int = tx_defaults.max_gas_amount,
        gas_unit_price: int = tx_defaults.gas_unit_price,
        gas_currency_code: str = tx_defaults.gas_currency_code,
        timeout_in_s: int = tx_defaults.timeout_in_s
    ) -> Dict[str, Any]:
        """Generate and return request for transaction

        Parameters
        ----------
        sender : str
            Signer of transaction
        payload : dict from str to Any
            Transaction payload data
        max_gas_amount : int, optional
            Maximum amount of gas to pay
        gas_unit_price : int, optional
            Unit price of gas
        gas_currency_code : str, optional
            Gas currency specifier
        timeout_in_s : int, optional
            How long to wait before transaction expires

        Returns
        -------
        dict from str to Any
            Transaction request
        """
        account_data = self.account(sender)
        seq_number = int(account_data[account_fields.sequence_number])
        timeout_stamp = str(int(time.time()) + timeout_in_s)
        return {
            tx_fields.sender: hex_leader(sender),
            tx_fields.sequence_number: str(seq_number),
            tx_fields.max_gas_amount: str(max_gas_amount),
            tx_fields.gas_unit_price: str(gas_unit_price),
            tx_fields.gas_currency_code: gas_currency_code,
            tx_fields.expiration_timestamp_secs: timeout_stamp,
            tx_fields.payload: payload
        }

    def sign_tx(
        self,
        account_from: Account,
        tx_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sign transaction request in preparation for submission

        Parameters
        ----------
        account_from : ultima.chain.account.Account
            Signing account
        tx_request : dict from str to Any
            Transaction request per
            :meth:`~chain.client.RestClient.generate_tx`

        Returns
        -------
        dict from str to Any
            Signed transaction request
        """
        response = self.get_post_response(
            [rest_path_elems.transactions, rest_path_elems.signing_message],
            json=tx_request
        )
        assert response.status_code == rest_codes.success. response.text
        to_sign = bytes.fromhex(
            response.json()[rest_response_fields.message][start_byte:]
        )
        signature = account_from.signing_key.sign(to_sign).signature
        tx_request[tx_fields.signature] = {
            tx_sig_fields.type: tx_sig_fields.ed25519_signature,
            tx_sig_fields.public_key: hex_leader(account_from.pub_key()),
            tx_sig_fields.signature: hex_leader(signature.hex())
        }
        return tx_request

    def submit_tx(
        self,
        tx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit signed transaction to blockchain

        Parameters
        ----------
        tx : dict from str to Any
            Signed transaction

        Returns
        -------
        dict from str to Any
            REST post response JSON
        """
        headers = {h_fields.content_type, h_fields.application_json}
        response = self.get_post_response(
            rest_path_elems.transactions,
            headers=headers,
            json=tx
        )
        assert response.status_code == rest_codes.processing, response.text
        return response.json()

    def tx_pending(
        self,
        tx_hash: str
    ) -> bool:
        """Return True if tx not found or if pending

        Parameters
        ----------
        tx_hash : str
            Transaction hash

        Returns
        -------
        True
            If transaction is not found or pending
        """
        response = self.get_request_response([
            rest_path_elems.transactions,
            tx_hash
        ])
        if response.status_code == rest_codes.not_found:
            return True
        assert response.status_code == rest_codes.success, response.text
        return response.json()[rest_response_fields.type] == \
            rest_response_fields.pending_transaction

    def wait_for_tx(
        self,
        tx_hash: str,
        time_in_s: int = tx_defaults.timeout_in_s
    ) -> None:
        """Wait for transaction to clear

        Parameters
        ----------
        tx_hash : str
            Transaction hash
        time_in_s : int, optional
            How long to wait before failure
        """
        count = 0
        while self.tx_pending(tx_hash):
            assert count < time_in_s, e_msgs.tx_timeout
            time.sleep(1)
            count += 1