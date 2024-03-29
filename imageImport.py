import ee
import logging
import multiprocessing
import requests
import shutil
from retry import retry
import pandas as pd
import json
from google.cloud import storage
from tqdm import tqdm

ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')

Tile = 136
y = 2021

def stretchImage(image, scale ,bounds):
  percentiles = [1, 99]
  bandNames = image.bandNames()
  scale =2*scale
  bounds = bounds
  imageMask = image.select(0).mask()

  minMax = image.updateMask(imageMask).reduceRegion(
    reducer= ee.Reducer.percentile(percentiles),
    geometry= bounds,
    scale= scale
    )


  def func_sfu(bandName):
      bandName = ee.String(bandName)
      min = ee.Number(minMax.get(bandName.cat('_p').cat(ee.Number(percentiles[0]).format())))
      max = ee.Number(minMax.get(bandName.cat('_p').cat(ee.Number(percentiles[1]).format())))

      return image.select(bandName).subtract(min).divide(max.subtract(min))

  bands = bandNames.map(func_sfu)

  return ee.ImageCollection(bands).toBands().rename(bandNames)


@retry(tries=10,delay=1,backoff=2)
def getResult(index,blobID):
    year = y
    RGB = True
    SNG = True
    tiff = False

    df1 = df.loc[df['blobID'] == blobID]
    imgid = str(df1['image_id'].values[0])
    centroid = df1['centroid'].values[0]

    centerpoint = ee.Geometry.Point(json.loads(centroid)['coordinates'])
    region = centerpoint.buffer(100).bounds()

    if RGB:
        image = stretchImage(ee.Image(imgid)
                        .clip(region)
                         .select(['B4', 'B3', 'B2'])
                        .resample('bicubic').divide(10000), 3, region).visualize(min=0, max=1)

        url = image.getThumbURL({
            'region': region,
            'dimensions': '256x256',
            'format': 'png'})

        r = requests.get(url, stream=True)
        if r.status_code != 200:
            r.raise_for_status()
        filename = 'BlobpngRGB'+ str(year)+'Tile'+str(i)+'/' + str(blobID) + '_Tile'+str(i)+'_' + str(year) + '_RGB.png'
        storage_client = storage.Client()
        bucket = storage_client.bucket('wwf-sand-budget')
        blob = bucket.blob(filename)
        blob.upload_from_file(r.raw)

    if SNG:
        image = stretchImage(ee.Image(imgid)
                        .clip(region)
                            .select(['B12','B8','B3'])
                        .resample('bicubic').divide(10000), 3, region).visualize(min=0, max=1)
        url = image.getThumbURL({
            'region': region,
            'dimensions': '256x256',
            'format': 'png'})

        r = requests.get(url, stream=True)
        if r.status_code != 200:
            r.raise_for_status()
        filename = 'BlobpngSNG'+ str(year)+'Tile'+str(i)+'/' + str(blobID) + '_Tile'+str(i)+'_' + str(year) + '_SNG.png'
        storage_client = storage.Client()
        bucket = storage_client.bucket('wwf-sand-budget')
        blob = bucket.blob(filename)
        blob.upload_from_file(r.raw)

    if tiff:
        image = (ee.Image(imgid)
                             .clip(region)
                             .select(['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12'])
                             .resample('bicubic').divide(10000))
        ee.batch.Export.image.toCloudStorage(
            image=image,
            description= str(blobID) + '_Tile' + str(i) + '_' + str(year) + '.tiff',
            bucket='wwf-sand-budget',
            filenamePrefix = 'Blobtiff' + str(year) + 'Tile' + str(i) + '/' + str(blobID) + '_Tile' + str(i) + '_' + str(year) + '.tiff'
        ).start()


    # with open(filename, 'wb') as out_file:
    #     shutil.copyfileobj(r.raw, out_file)
    # print("Done")
    file1 = open("doneID.txt", "a")
    file1.close()

if __name__ == '__main__':
  df = pd.read_pickle('Blobs2021df')
  #define Tile as i in [0,270]
  i = Tile
  df = df[df['Tile']==i]
  logging.basicConfig()
  items = df['blobID']

  pool = multiprocessing.Pool(25)
  pool.starmap(getResult, enumerate(items))

  pool.close()