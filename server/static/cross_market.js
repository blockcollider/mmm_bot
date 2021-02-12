function clearInputWithId(inputIdToClear, item) {
    if (item === 'counter') {
        var counter = $('#wallet_counter_currency_name').val().trim();

        var base = $('#wallet_base_currency_name').val().trim();
        console.log('counter', counter, 'base', base);

        $('#wallet_base_currency_name').empty();
        if (counter === base) {
            $('#wallet_base_currency_wallet').val('');
        }

        var allAssets = [ 'BTC', 'ETH', 'LSK', 'NEO', 'WAV', 'DAI' ];
        allAssets.forEach(function(asset) {
            if (asset !== counter) {
                var ele = '';
                if (asset === base) {
                    ele = `<option value="${asset}" selected> ${asset} </option>`;
                } else {
                    ele = `<option value="${asset}"> ${asset} </option>`;
                }
                $('#wallet_base_currency_name').append(ele);
            }
        });
    }
    $(`#${inputIdToClear}`).val('');
}

function validateBcParams() {
    var exchange_destination_miner_address = $('#exchange_destination_miner_address').val().trim().toLowerCase();
    var exchange_destination_miner_scookie = $('#exchange_destination_miner_scookie').val().trim();
    var exchange_destination_nrg_public_key = $('#exchange_destination_nrg_public_key').val().trim().toLowerCase();

    if (!exchange_destination_miner_address) {
        return;
    }
    if (!exchange_destination_nrg_public_key) {
        return;
    }

    function onSuccess(data) {
        console.log('test result', data);
        if (data.is_valid) {
            var balance = data.is_valid.result;
            $('#exchange_destination_miner_address_status').removeClass('fa-times');
            $('#exchange_destination_miner_address_status').addClass('fa-check');
            $('#exchange_destination_miner_address_status').css('color', 'green');

            $('#balance-pre').text('Overline Balance: ' + JSON.stringify(balance, null, 2));
        } else {
            $('#exchange_destination_miner_address_status').addClass('fa-times');
            $('#exchange_destination_miner_address_status').removeClass('fa-check');
            $('#exchange_destination_miner_address_status').css('color', 'red');
        }
    }

    $.ajax({
        type: 'GET',
        url: '/test_bc_params',
        data: {
            exchange_destination_miner_address: exchange_destination_miner_address,
            exchange_destination_nrg_public_key: exchange_destination_nrg_public_key,
            exchange_destination_miner_scookie: exchange_destination_miner_scookie
        },
        success: onSuccess,
        failure: function(errMsg) {
            alert(errMsg);
        }
    });
}

function validateAPIKeys() {
    var exchange_source_api_key = $('#exchange_source_api_key').val().trim();
    var exchange_source_api_secret = $('#exchange_source_api_secret').val().trim();

    function markKeysAsInvalid() {
        $('#exchange_source_api_key_status').removeClass('fa-check');
        $('#exchange_source_api_key_status').addClass('fa-times');
        $('#exchange_source_api_key_status').css('color', 'red');

        $('#exchange_source_api_secret_status').removeClass('fa-check');
        $('#exchange_source_api_secret_status').addClass('fa-times');
        $('#exchange_source_api_secret_status').css('color', 'red');
    }

    function onSuccess(data) {
        console.log('test result', data);
        if (data.is_valid) {
            $('#exchange_source_api_key_status').removeClass('fa-times');
            $('#exchange_source_api_key_status').addClass('fa-check');
            $('#exchange_source_api_key_status').css('color', 'green');

            $('#exchange_source_api_secret_status').removeClass('fa-times');
            $('#exchange_source_api_secret_status').addClass('fa-check');
            $('#exchange_source_api_secret_status').css('color', 'green');
        } else {
            markKeysAsInvalid();
            alert('Invalid Keys: ' + data.reason);
        }
    }

    $.ajax({
        type: 'GET',
        url: '/test_binance_keys',
        data: {
            exchange_source_api_key: exchange_source_api_key,
            exchange_source_api_secret: exchange_source_api_secret
        },
        success: onSuccess,
        failure: function(errMsg) {
            markKeysAsInvalid();
            alert(errMsg);
        }
    });
}

function getWallets() {
    var exchangeSourceName = $('#exchange_source_name').val().trim().toLowerCase();
    var apiKey = $('#exchange_source_api_key').val().trim();
    var apiSecret = $('#exchange_source_api_secret').val().trim();
    var base = $('#wallet_base_currency_name').val().trim();
    var counter = $('#wallet_counter_currency_name').val().trim();
    if (!apiKey || !apiSecret) {
        alert('Please fill the API Key and API Secret');
    }

    var reqBody = {
        exchange_name: exchangeSourceName,
        api_key: apiKey,
        api_secret: apiSecret,
        assets: [ base, counter ]
    };

    function onSuccess(data) {
        console.log('Loaded the address', data);
        $('#wallet_base_currency_wallet').val(data[base]);
        $('#wallet_counter_currency_wallet').val(data[counter]);

        $('#wallet_base_currency_private_key').val('');
        $('#wallet_counter_currency_private_key').val('');

        $('#wallet_base_currency_private_key').prop('disabled', true);
        $('#wallet_counter_currency_private_key').prop('disabled', true);
    }

    $.ajax({
        type: 'POST',
        url: '/exchange_wallet',
        data: JSON.stringify(reqBody),
        contentType: 'application/json; charset=utf-8',
        dataType: 'json',
        success: onSuccess,
        failure: function(errMsg) {
            alert(errMsg);
        }
    });
}

$(document).ready(function() {
    validateBcParams();
});
