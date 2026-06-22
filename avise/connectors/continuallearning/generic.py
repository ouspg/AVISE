"""Generic REST API Connector for Continual Learning systems."""

import logging
import requests

from .base import BaseCLConnector
from ...registry import connector_registry
from ...utils import ansi_colors

logger = logging.getLogger(__name__)


@connector_registry.register("generic-rest-cl")
class GenericRESTCLConnector(BaseCLConnector):
    """Connector for communicating with custom Continual Learning REST APIs.

    Used by Continual Learning SETs for querying a target model.
    """

    name = "generic-rest-cl"

    # Modalities whose samples may carry raw binary content (e.g. image bytes,
    # audio waveforms) that the target API expects as a multipart file upload
    # rather than as form-encoded fields. "numeric" and "text" samples are
    # always sent as plain form data.
    _FILE_BASED_MODALITIES = {"image", "audio", "video", "multimodal"}

    def __init__(self, config: dict):
        """Initialize the Generic REST API connector.

        Args:
            config: Dictionary containing data from Connector configuration JSON.
        """
        self.config = config
        try:
            self.base_url = config["target_model"]["api_endpoint"]["base"].get(
                "url", ""
            )
            if not self.base_url:
                raise ValueError(
                    '[["target_model"]"api_endpoint"]["base"]["url"] is not configured in the provided Generic REST CL Connector configuration file.'
                )
            if not isinstance(self.base_url, str):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                )
            self.base_headers = config["target_model"]["api_endpoint"]["base"].get(
                "headers", ""
            )
            self.base_batch_handling = config["target_model"]["api_endpoint"][
                "base"
            ].get("batch_handling", False)

            self.base_method = config["target_model"]["api_endpoint"]["base"].get(
                "method", "POST"
            )
            if not self.base_method:
                self.base_method = "POST"
            if not isinstance(self.base_method, str):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                )
            self.time_out = config["target_model"]["api_endpoint"]["base"].get(
                "time_out", 30
            )
            if not isinstance(self.time_out, int):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["time_out"] must be an int in the Generic REST CL Connector configuration file.'
                )
            self.base_pred_field = config["target_model"]["api_endpoint"]["base"].get(
                "prediction_field", ""
            )
            if not isinstance(self.base_pred_field, str):
                self.base_pred_field = str(self.base_pred_field)
            if not self.base_pred_field:
                raise ValueError(
                    '["target_model"]["api_endpoint"]["base"]["prediction_field"] is required in the Generic REST CL Connector configuration file. It is the API response field that contains the target model´s prediction or response.'
                )
            self.base_confidence_field = config["target_model"]["api_endpoint"][
                "base"
            ].get("confidence_field", None)
            if self.base_confidence_field:
                if not isinstance(self.base_confidence_field, str):
                    self.base_confidence_field = str(self.base_confidence_field)
            self.base_probabilities_field = config["target_model"]["api_endpoint"][
                "base"
            ].get("probabilities_field", None)
            if self.base_probabilities_field:
                if not isinstance(self.base_probabilities_field, str):
                    self.base_probabilities_field = str(self.base_probabilities_field)
            if "train" in config["target_model"]["api_endpoint"]:
                if (
                    config["target_model"]["api_endpoint"]["train"].get("url")
                    is not None
                ):
                    self.train_url = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("url")
                    if not isinstance(self.train_url, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                        )
                    self.train_headers = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("headers")
                    self.train_batch_handling = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("batch_handling", False)
                    self.train_method = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("method", "POST")
                    if not isinstance(self.train_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )
            else:
                self.train_url = None
                self.train_headers = None
                self.train_method = None
                self.train_batch_handling = None
            if "inference" in config["target_model"]["api_endpoint"]:
                if (
                    config["target_model"]["api_endpoint"]["inference"].get("url")
                    is not None
                ):
                    self.infer_url = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("url")
                    if not isinstance(self.infer_url, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                        )
                    self.infer_headers = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("headers")
                    self.infer_batch_handling = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("batch_handling", False)
                    self.infer_method = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("method", "POST")
                    if not isinstance(self.infer_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )

                    self.infer_pred_field = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("prediction_field", None)
                    if self.infer_pred_field:
                        if not isinstance(self.infer_pred_field, str):
                            self.infer_pred_field = str(self.infer_pred_field)
                    self.infer_confidence_field = config["target_model"][
                        "api_endpoint"
                    ]["inference"].get("confidence_field", None)
                    if self.infer_confidence_field:
                        if not isinstance(self.infer_confidence_field, str):
                            self.infer_confidence_field = str(
                                self.infer_confidence_field
                            )
                    self.infer_probabilities_field = config["target_model"][
                        "api_endpoint"
                    ]["inference"].get("probabilities_field", None)
                    if self.infer_probabilities_field:
                        if not isinstance(self.infer_probabilities_field, str):
                            self.infer_probabilities_field = str(
                                self.infer_probabilities_field
                            )
            else:
                self.infer_url = None
                self.infer_headers = None
                self.infer_batch_handling = None
                self.infer_method = None
                self.infer_pred_field = None
                self.infer_confidence_field = None
                self.infer_probabilities_field = None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while initializing GenericRESTCLConnector: {e}{ansi_colors['reset']}"
            )
        logger.info(
            f"  Generic REST API Connector Initialized for Continual Learning Target System."
        )
        logger.info(f"  Base URL: {self.base_url}")

    def _post(self, url: str, headers, data, timeout: int, files=None) -> dict:
        """Send a single POST request and return the parsed JSON body.

        `files` is forwarded to `requests.post()` as-is. When `files` is a
        non-empty dict, `requests` automatically sends the request as
        multipart/form-data (with `data` becoming the regular form fields
        alongside the file parts). When `files` is None, behavior is
        unchanged from before: a plain form-encoded POST body.
        """
        if headers is None:
            response = requests.post(url=url, data=data, files=files, timeout=timeout)
        else:
            response = requests.post(
                url=url, data=data, files=files, headers=headers, timeout=timeout
            )
        return response.json()

    def _build_request_payload(self, payload, data_modality: str):
        """Shape one sample (`payload`) into (files, form_data) for `requests.post()`.

        "numeric" and "text" samples are sent exactly as before: as a single
        form-encoded body, with no file part — (None, payload).

        "image", "audio", "video", and "multimodal" samples may contain raw
        binary content (e.g. image bytes) that the target API expects as a
        multipart file upload (matching, e.g., FastAPI's `UploadFile`) rather
        than as a form field. If `payload` is a dict, it's split key by key:
        values that are bytes/bytearray, a file-like object (anything with a
        `.read()` method), or an already-built `requests` file tuple (e.g.
        `(filename, fileobj, content_type)`) go into `files`; every remaining
        (scalar) key/value — e.g. `top_k`, `true_label` — goes into `data` as
        a normal form field. If `payload` isn't a dict (e.g. it's already raw
        image bytes with no accompanying metadata), it's sent whole as a
        single file under the key "file".

        Returns:
            (files, form_data) tuple. Either element may be None if there's
            nothing of that kind to send.
        """
        if data_modality not in self._FILE_BASED_MODALITIES:
            return None, payload

        if not isinstance(payload, dict):
            return {"file": payload}, None

        files, form_data = {}, {}
        for key, value in payload.items():
            if (
                isinstance(value, (bytes, bytearray))
                or hasattr(value, "read")
                or isinstance(value, tuple)
            ):
                files[key] = value
            else:
                form_data[key] = value

        return (files or None), (form_data or None)

    def _post_data(
        self,
        url: str,
        headers,
        data: list,
        timeout: int,
        batch_handling: bool,
        data_modality: str,
    ) -> dict:
        """Send `data` to `url`, honoring whether the endpoint can handle batches
        and shaping each request to match `data_modality`.

        If `batch_handling` is True, `data` is sent as a single request, in
        one call. For file-based modalities, `data` itself is split into a
        files part and a form-data part (see `_build_request_payload`); for
        "numeric"/"text" it's sent unchanged as the form-encoded body. The
        parsed JSON response is returned unmodified.

        If `batch_handling` is False, the endpoint can only handle one item
        per request, so `data` is iterated over and each item is sent as its
        own request — shaped per-item the same way as above. The individual
        responses are reconstructed into a single dict shaped like a batch
        response: {"results": [<per-item response>, ...]}, with one entry per
        item, in the same order as `data`. This keeps the return shape
        consistent regardless of whether the target endpoint natively
        batches or not.
        """
        if batch_handling:
            files, form_data = self._build_request_payload(data, data_modality)
            return self._post(url, headers, form_data, timeout, files=files)

        results = []
        for item in data:
            files, form_data = self._build_request_payload(item, data_modality)
            results.append(self._post(url, headers, form_data, timeout, files=files))
        return {"results": results}

    def query(self, data: list, data_modality: str, task="inference") -> dict:
        """Function for making query requests to the target REST API.

        Arguments:
            data: Dictionary containing the required data for the API request.
            data_modality: One of "numeric", "text", "image", "audio", "video",
                or "multimodal". For "numeric"/"text", each item is sent as a
                plain form-encoded POST body, same as before. For the other
                (file-based) modalities, each item is split into a multipart
                file part and a form-data part — e.g. an `{"image": <bytes>,
                "top_k": 5, "true_label": 3}` item is sent with "image" as an
                uploaded file and "top_k"/"true_label" as regular form fields.
                See `_build_request_payload` for the exact splitting rules.
            task: "inference" for inference query | "train" for training query.

        Returns:
            API response as a dict.

            For "inference" tasks against an endpoint with batch_handling=True,
            the dict is the raw batch response, enriched with top-level
            "prediction", "confidence", and "probabilities" fields.

            For "inference" tasks against an endpoint with batch_handling=False,
            `data` was sent one item at a time, so the dict instead holds a
            "results" key containing a list of per-item response dicts (one per
            input item, in order), each individually enriched with "prediction",
            "confidence", and "probabilities".
        """
        if data_modality not in (
            "numeric",
            "text",
            "image",
            "audio",
            "video",
            "multimodal",
        ):
            raise ValueError(
                'Tried to query the target API with an invalid data modality. Use one of the following: "numeric", "text", "image", "audio", "video", or "multimodal"'
            )
        try:
            if task == "inference":
                if self.infer_url:
                    if self.infer_method == "POST":
                        response_data = self._post_data(
                            self.infer_url,
                            self.infer_headers,
                            data,
                            self.time_out,
                            self.infer_batch_handling,
                            data_modality,
                        )
                        items = (
                            [response_data]
                            if self.infer_batch_handling
                            else response_data["results"]
                        )
                        for item in items:
                            item["prediction"] = item.get(self.infer_pred_field)
                            item["confidence"] = item.get(self.infer_confidence_field)
                            item["probabilities"] = item.get(
                                self.infer_probabilities_field
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for inference requests in CL Generic REST Connector."
                        )
                else:
                    # Use the base url for inference request
                    if self.base_method == "POST":
                        response_data = self._post_data(
                            self.base_url,
                            self.base_headers,
                            data,
                            self.time_out,
                            self.base_batch_handling,
                            data_modality,
                        )
                        items = (
                            [response_data]
                            if self.base_batch_handling
                            else response_data["results"]
                        )
                        for item in items:
                            item["prediction"] = item.get(self.base_pred_field)
                            item["confidence"] = item.get(self.base_confidence_field)
                            item["probabilities"] = item.get(
                                self.base_probabilities_field
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for inference requests in CL Generic REST Connector."
                        )

            elif task == "train":
                if self.train_url:
                    # Make a traning request
                    if self.train_method == "POST":
                        response_data = self._post_data(
                            self.train_url,
                            self.train_headers,
                            data,
                            self.time_out,
                            self.train_batch_handling,
                            data_modality,
                        )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for training requests in CL Generic REST Connector."
                        )
                else:
                    # Use the base url for training request
                    if self.base_method == "POST":
                        response_data = self._post_data(
                            self.base_url,
                            self.base_headers,
                            data,
                            self.time_out,
                            self.base_batch_handling,
                            data_modality,
                        )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for training requests in CL Generic REST Connector."
                        )
            else:
                raise ValueError(
                    'Only "inference" and "train" are valid values for `task` in GenericRESTCLConnector.query()'
                )

        except Exception as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while querying Continual Learning system: {e}{ansi_colors['reset']}"
            )
            raise RuntimeError(
                "Failed to query the Continual Learning target system due to an error."
            ) from e
        return response_data

    def status_check(self):
        """Check if the configured API endpoint(s) is available with a GET request."""
        base_healthy = False if self.base_url else True
        inference_healthy = False if self.infer_url else True
        train_healthy = False if self.train_url else True

        if self.infer_url:
            # Perform status check for the inference endpoint
            response_infer = (
                requests.get(self.infer_url, timeout=self.time_out)
                if self.infer_headers is None
                else requests.get(
                    self.infer_url,
                    headers=self.infer_headers,
                    timeout=self.time_out,
                )
            )
            response_infer = response_infer.json()
            try:
                if response_infer.status_code == 200:
                    inference_healthy = True
            except (KeyError, ValueError, AttributeError) as e:
                logger.error(
                    f"{ansi_colors['red']}ERROR while doing a status check on the configured inference API endpoint: {e}{ansi_colors['reset']}"
                )

        if self.base_url:
            # Perform status check for the base endpoint
            response_base = (
                requests.get(self.base_url, timeout=self.time_out)
                if self.base_headers is None
                else requests.get(
                    self.base_url, headers=self.base_headers, timeout=self.time_out
                )
            )
            response_base = response_base.json()
            try:
                if response_base.status_code == 200:
                    base_healthy = True
            except (KeyError, ValueError, AttributeError) as e:
                logger.error(
                    f"{ansi_colors['red']}ERROR while doing a status check on the configured base API endpoint: {e}{ansi_colors['reset']}"
                )

        if self.train_url:
            # Perform status check for the training endpoint
            response_train = (
                requests.get(self.train_url, timeout=self.time_out)
                if self.train_headers is None
                else requests.get(
                    self.train_url,
                    headers=self.train_headers,
                    timeout=self.time_out,
                )
            )
            response_train = response_train.json()
            try:
                if response_train.status_code == 200:
                    train_healthy = True
            except (KeyError, ValueError, AttributeError) as e:
                logger.error(
                    f"{ansi_colors['red']}ERROR while doing a status check on the configured training API endpoint: {e}{ansi_colors['reset']}"
                )

        if all((base_healthy, inference_healthy, train_healthy)):
            logger.info("All target API status checks passed succesfully!")
        else:
            failed_urls = []
            if not base_healthy:
                failed_urls.append(self.base_url)
            if not inference_healthy:
                failed_urls.append(self.infer_url)
            if not train_healthy:
                failed_urls.append(self.train_url)

            logger.info(
                "Target API status check(s) did not pass for the following URLs: %s",
                ", ".join(failed_urls),
            )
            logger.info(
                "Continuing with SET execution anyway, since all API endpoints may not allow GET requests..."
            )

        return True
