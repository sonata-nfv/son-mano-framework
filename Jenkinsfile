pipeline {
  agent any
  stages {
    stage('Build') {
      parallel {
        stage('Service Lifecycle Manager') {
          steps {
            echo 'Building Service Lifecycle Manager container'
            sh './pipeline/build/servicelifecyclemanagement.sh'
          }
        }
        stage('Function Lifecycle Manager') {
          steps {
            echo 'Building Function Lifecycle Manager container'
            sh './pipeline/build/functionlifecyclemanagement.sh'
          }
        }
        stage('Plugin Manager') {
          steps {
            echo 'Building Plugin Manager container'
            sh './pipeline/build/pluginmanager.sh'
          }
        }
        stage('sonmanobase') {
          steps {
            echo 'Building sonmanobase container'
            sh './pipeline/build/sonmanobase.sh'
          }
        }
        stage('Specifc Manager Registry') {
          steps {
            echo 'Building Specific Manager Registry container'
            sh './pipeline/build/specificmanagerregistry.sh'
          }
        }
        stage('Placement Executive') {
          steps {
            echo 'Building Placement Executive container'
            sh './pipeline/build/placementexecutive.sh'
          }
        }
        stage('Placement Plugin') {
          steps {
            echo 'Building Placement Plugin container'
            sh './pipeline/build/placementplugin.sh'
          }
        }
      }
    }
    stage('Unittest Dependencies') {
      steps {
        sh './pipeline/unittest/create_dependencies.sh'
      }
    }
    stage('Unittest Plugin Manager') {
      steps {
        sh './pipeline/unittest/pluginmanager_unittest.sh'
      }
    }
    stage('Uniittest next dependencies') {
      steps {
        sh './pipeline/unittest/create_pm_dependency.sh'
      }
    }
    stage('Unittest Specifc Manager Registry') {
      steps {
        sh './pipeline/unittest/specificmanagerregistry_unittest.sh'
      }
    }
    stage('Unittest second phase'){
      parallel {
        stage('Unittest Service Lifecycle Manager') {
          steps {
            sh './pipeline/unittest/servicelifecyclemanager_unittest.sh'
          }
        }
        stage('Unittest Function Lifecycle Manager') {
          steps {
            sh './pipeline/unittest/functionlifecyclemanager_unittest.sh'
          }
        }
        stage('Unittest sonmanobase') {
          steps {
            sh './pipeline/unittest/sonmanobase_unittest.sh'
          }
        }
        stage('Unittest Placement Executive') {
          steps {
            sh './pipeline/unittest/placementexecutive_unittest.sh'
          }
        }
        stage('Unittest Placement Plugin') {
          steps {
            sh './pipeline/unittest/placementplugin_unittest.sh'
          }
        }
      }
    }
  }
  post {
    always {
      echo 'Clean Up'
      sh './pipeline/unittest/clean_environment.sh'
    }
    success {
        emailext (
          subject: "SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>SUCCESS: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
        recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
      }
    failure {
      emailext (
          subject: "FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
          body: """<p>FAILED: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':</p>
            <p>Check console output at &QUOT;<a href='${env.BUILD_URL}'>${env.JOB_NAME} [${env.BUILD_NUMBER}]</a>&QUOT;</p>""",
          recipientProviders: [[$class: 'DevelopersRecipientProvider']]
        )
    }  
  }
}