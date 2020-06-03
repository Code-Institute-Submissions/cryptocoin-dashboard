import os, json, locale
import pandas as pd
import numpy as np
import plotly
import plotly.graph_objs as go #Pie Chart
from flask import Flask, render_template, redirect, request, url_for, jsonify
from flask_pymongo import PyMongo
from pymongo.mongo_client import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from iexfinance.stocks import Stock, get_historical_data
from calculations import value_change_coins

def prepare_buy_object(form_object,user_data):
    document_object = {}
    document_object["user_id"]=user_data["_id"]
    document_object["symbol"]=form_object["submit-buy-coin-symbol"]
    document_object["name"]=form_object["submit-buy-coin-name"]
    document_object["type"]="purchase"
    now = datetime.utcnow()
    document_object["date"]=datetime.utcnow()
    document_object["ticker"]=float(form_object["ticket-entry-number"])
    document_object["price"]=float(form_object["submit-buy-coin-bid-price"].replace('US$ ','').replace(',',''))
    return document_object

def prepare_sell_object(form_object,user_data):
    document_object = {}
    document_object["user_id"]=user_data["_id"]
    document_object["symbol"]=form_object["submit-sell-coin-symbol"]
    document_object["name"]=form_object["submit-sell-coin-name"]
    document_object["type"]="sale"
    now = datetime.utcnow()
    document_object["date"]=datetime.utcnow()
    document_object["ticker"]=float(form_object["sell-ticket-entry-number"])*-1
    document_object["price"]=float(form_object["submit-sell-coin-ask-price"].replace('US$ ','').replace(',',''))
    return document_object

def insert_transaction_to_db(mongo,new_doc,user_data):
    user_id=user_data['_id']
    transactions=mongo.db.transactions
    inserted_doc=transactions.insert_one(new_doc)
    latest_id= inserted_doc.inserted_id
    latest_transaction=mongo.db.transactions.find_one({'_id': latest_id})
    transaction_coin=new_doc['symbol']
    transaction_ticker=float(new_doc['ticker'])
    user_cash=user_data['cash']
    available_earned=user_data['cash_earned']
    user_wallet=user_data['wallet']
    user_coins=user_wallet['coins']
    current_coins_number=float(user_wallet['total_coins'])
    available_ticker=float(user_coins[transaction_coin]['total_ticker'])
    if new_doc['type']=='purchase':
        cash_spent=new_doc['price']*transaction_ticker
        mongo.db.users.update(
            { '_id' : ObjectId(user_id) },
            { '$set' : { 'cash' : user_cash - cash_spent }
        })
        if user_data['cash'] < 0.00:
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'cash' : 0.00 }
            })
        if transaction_coin in user_coins:
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$push' : { 'wallet.coins.'+transaction_coin+'.transactions' : latest_transaction }
            })
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'wallet.coins.'+transaction_coin+'.total_ticker' : available_ticker + transaction_ticker }
            })
            return
        else:
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'wallet.coins.'+transaction_coin : { 'symbol':transaction_coin, 'total_ticker' : new_doc['ticker'], 'transactions': [latest_transaction] }}
                })
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'wallet.total_coins' : current_coins_number+1 }
                })
            return
    if new_doc['type']=='sale':
        cash_exchange=new_doc['price']*transaction_ticker
        mongo.db.users.update(
            { '_id' : ObjectId(user_id) },
            { '$set' : { 'cash' : user_cash - cash_exchange }
        })
        value_change_coins_obj = value_change_coins(user_wallet)
        value_change_transaction_coin = float(value_change_coins_obj[transaction_coin])
        cash_earned = value_change_transaction_coin * transaction_ticker *-1 
        mongo.db.users.update(
            { '_id' : ObjectId(user_id) },
            { '$set' : { 'cash_earned' : available_earned + cash_earned }
        })
        ticker_left = available_ticker + transaction_ticker
        if ticker_left < 0.01:
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$unset' : { 'wallet.coins.'+transaction_coin : ''}
                })
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'wallet.total_coins' : current_coins_number-1 }
                })
            return
        elif ticker_left >= 0.01:
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$push' : { 'wallet.coins.'+transaction_coin+'.transactions' : latest_transaction }
            })
            mongo.db.users.update(
                { '_id' : ObjectId(user_id) },
                { '$set' : { 'wallet.coins.'+transaction_coin+'.total_ticker' : available_ticker + transaction_ticker }
            })
            return
